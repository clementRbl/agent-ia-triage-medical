"""Deploiement du service de triage sur Modal.

Pourquoi Modal : le POC doit exposer un endpoint cloud servi par vLLM, donc
sur GPU. Le plan gratuit de Modal renouvelle 30 $ de credits chaque mois sans
carte bancaire, ce qui couvre tres largement une demonstration. Les offres
gratuites concurrentes sont limitees au CPU, ou vLLM perdrait sa raison
d'etre et les mesures de latence tout leur sens.

Architecture : deux fonctions. vLLM tourne sur le GPU et n'accepte que les
appels portant le jeton du proxy Modal ; l'application FastAPI tourne sur un
petit conteneur CPU, verifie la cle d'API puis appelle vLLM avec ce jeton.
Avec un seul conteneur GPU, n'importe quelle requete anonyme -- meme un 401 --
allumait l'A10G avant la verification de la cle : un appel toutes les quatre
minutes suffisait a le garder allume en continu, a la charge du compte.

Deploiement :
    uv run modal deploy deploiement/modal_app.py
"""

from __future__ import annotations

import os
import subprocess
import time
from typing import Any

import modal

APPLICATION = "triage-chsa"

# Modele de base et adaptateur, tous deux tires du Hub au demarrage. Les
# epingler par revision serait preferable en production : une image qui
# resout « derniere version » ne se redeploie pas a l'identique.
#
# Ces valeurs sont lues **au deploiement**, sur le poste qui lance la commande,
# puis inscrites dans l'environnement de l'image (voir `.env` plus bas). Sans
# cela le conteneur, qui reevalue ce module a son demarrage, ne verrait aucune
# de ces variables et repartirait sur ses valeurs par defaut.
MODELE_BASE = os.environ.get("TRIAGE_MODELE_BASE", "Qwen/Qwen3-1.7B-Base")
ADAPTATEUR = os.environ.get("TRIAGE_ADAPTATEUR", "")

# Deux noms distincts, et c'est delibere : le modele de base et le modele
# affine ne doivent jamais repondre sous la meme etiquette. S'ils la
# partageaient et que l'adaptateur venait a manquer, vLLM servirait le modele
# nu sous le nom du modele affine -- il repondrait, de facon plausible, et
# fausse. Avec deux noms, la meme situation produit une erreur franche.
NOM_SERVI = "triage-qwen3-1.7b"
NOM_BASE = "qwen3-base"

PORT_VLLM = 8000
URL_VLLM_LOCALE = f"http://127.0.0.1:{PORT_VLLM}"

# Le rang de l'adaptateur doit etre declare a vLLM : au-dela de la valeur
# annoncee, le chargement echoue au premier appel et non au demarrage.
RANG_LORA = 16

# Delai de patience au demarrage : le telechargement des poids depuis le Hub
# peut prendre plusieurs minutes lors du tout premier demarrage a froid.
DELAI_DEMARRAGE_S = 600

# GPU. Mesure a l'appui, le T4 rend une latence mediane de 8,0 s la ou un A10G
# descend nettement plus bas : sa generation ne gere ni bfloat16 ni
# FlashAttention 2 -- vLLM retombe sur un noyau d'attention lent -- et sa bande
# passante memoire est 2,4 fois inferieure, ce qui domine en generation.
# L'A10G consomme davantage de credits a l'heure, mais le conteneur s'eteint
# apres cinq minutes d'inactivite : sur un POC sollicite par intermittence, la
# depense reelle reste tres en deca des 30 $ mensuels.
GPU = os.environ.get("TRIAGE_GPU", "A10G")

# Configuration lue au deploiement, figee dans les deux images.
CONFIGURATION = {
    "TRIAGE_MODELE_BASE": MODELE_BASE,
    "TRIAGE_ADAPTATEUR": ADAPTATEUR,
    "TRIAGE_GPU": GPU,
}

image_gpu = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(
        "vllm==0.11.0",
        # transformers est epingle sous la version 5 : vLLM 0.11 appelle
        # `all_special_tokens_extended`, retire depuis. Laisser pip resoudre
        # librement casse le serveur au demarrage, apres construction de
        # l'image -- soit le pire moment pour s'en apercevoir.
        "transformers>=4.55.2,<5",
        "httpx>=0.28",
    )
    .env(CONFIGURATION)
)

# L'API n'a besoin ni de vLLM ni de torch : une image legere demarre vite sur CPU.
image_api = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(
        "fastapi>=0.115",
        "httpx>=0.28",
        "pydantic>=2.10",
        "presidio-analyzer>=2.2",
        "presidio-anonymizer>=2.2",
        "pandas>=2.2",
    )
    .pip_install(
        "https://github.com/explosion/spacy-models/releases/download/"
        "fr_core_news_md-3.8.0/fr_core_news_md-3.8.0-py3-none-any.whl",
        "https://github.com/explosion/spacy-models/releases/download/"
        "en_core_web_md-3.8.0/en_core_web_md-3.8.0-py3-none-any.whl",
    )
    # Le code du service est embarque tel quel : l'image deployee et le depot
    # portent la meme revision, ce que /version rend verifiable.
    .add_local_python_source("triage", copy=True)
    .env(CONFIGURATION)
)

app = modal.App(APPLICATION)

# Le journal d'audit doit survivre au recyclage des conteneurs : un journal
# medical perdu a chaque mise a l'echelle ne prouverait rien.
journal = modal.Volume.from_name("triage-journal", create_if_missing=True)

# Les poids telecharges sont conserves d'un demarrage a l'autre : sans ce
# cache, chaque demarrage a froid retelecharge plusieurs gigaoctets.
poids = modal.Volume.from_name("triage-poids", create_if_missing=True)

# Secrets : jamais dans l'image, jamais dans le depot. `TRIAGE_CLES_API`
# protege l'endpoint, `VLLM_PROXY_CLE` et `VLLM_PROXY_SECRET` (jeton du proxy
# Modal) ouvrent l'acces a vLLM, `HF_TOKEN` autorise le telechargement d'un
# depot prive.
secrets = [
    modal.Secret.from_name(
        "triage-secrets",
        required_keys=["TRIAGE_CLES_API", "VLLM_PROXY_CLE", "VLLM_PROXY_SECRET"],
    )
]


def _commande_vllm(adaptateur: str) -> list[str]:
    return [
        "vllm",
        "serve",
        MODELE_BASE,
        # Toutes interfaces : le proxy Modal doit joindre le port. Il filtre
        # lui-meme les appels sans jeton avant d'allumer le conteneur.
        "--host",
        "0.0.0.0",
        "--port",
        str(PORT_VLLM),
        "--served-model-name",
        NOM_BASE,
        # Le POC sert des tableaux cliniques courts ; reserver 40 000 tokens de
        # contexte immobiliserait de la memoire pour rien.
        "--max-model-len",
        "2048",
        # Borne explicite : vLLM prechauffe son echantillonneur sur 256 requetes
        # simultanees par defaut, ce qui sature la memoire d'un petit GPU avant
        # meme la premiere requete reelle. Un service d'accueil n'a de toute
        # facon jamais 256 triages en vol.
        "--max-num-seqs",
        "16",
        "--gpu-memory-utilization",
        "0.90",
        "--enable-lora",
        "--max-lora-rank",
        str(RANG_LORA),
        "--lora-modules",
        f"{NOM_SERVI}={adaptateur}",
    ]


def _attendre_vllm(delai: int = DELAI_DEMARRAGE_S) -> None:
    """Bloque jusqu'a ce que vLLM reponde, ou echoue franchement.

    Sans cette attente, les premieres requetes tomberaient sur un serveur non
    demarre et le service repondrait 500 pendant plusieurs minutes apres
    chaque demarrage a froid.
    """
    import httpx

    limite = time.monotonic() + delai
    derniere_erreur: Exception | None = None
    while time.monotonic() < limite:
        try:
            if httpx.get(f"{URL_VLLM_LOCALE}/health", timeout=5.0).status_code == 200:
                return
        except httpx.HTTPError as erreur:
            derniere_erreur = erreur
        time.sleep(2.0)
    raise RuntimeError(f"vLLM n'a pas démarré en {delai} s ; dernière erreur : {derniere_erreur}")


def _verifier_adaptateur_servi() -> None:
    """Refuse de servir si le modele affine n'apparait pas dans vLLM.

    Un adaptateur qui ne se charge pas ne fait pas echouer vLLM : le serveur
    demarre, sert le modele de base et repond a tout. C'est exactement le genre
    de panne qu'aucune sonde de vivacite ne detecte, et qui produit des
    reponses plausibles et fausses.
    """
    import httpx

    reponse = httpx.get(f"{URL_VLLM_LOCALE}/v1/models", timeout=30)
    reponse.raise_for_status()
    disponibles = [modele["id"] for modele in reponse.json()["data"]]
    if NOM_SERVI not in disponibles:
        raise RuntimeError(
            f"L'adaptateur {NOM_SERVI!r} n'est pas servi par vLLM. "
            f"Modèles disponibles : {disponibles}"
        )


@app.function(
    image=image_gpu,
    gpu=GPU,
    volumes={"/root/.cache/huggingface": poids},
    secrets=secrets,
    timeout=3600,
    # Le conteneur s'eteint apres cinq minutes sans trafic : sur un POC
    # sollicite par intermittence, c'est ce qui tient dans les credits.
    scaledown_window=300,
    max_containers=1,
)
@modal.concurrent(max_inputs=8)
# requires_proxy_auth : sans le jeton, Modal repond 401 sans allumer le GPU.
@modal.web_server(PORT_VLLM, startup_timeout=DELAI_DEMARRAGE_S, requires_proxy_auth=True)
def vllm_serveur() -> None:
    """Sert le modele affine sur le GPU, joignable par l'API seulement."""
    adaptateur = os.environ.get("TRIAGE_ADAPTATEUR", "")
    if not adaptateur:
        # Mieux vaut ne pas demarrer que servir le modele nu : il repondrait
        # de facon plausible sans rien connaitre du bareme de triage.
        raise RuntimeError(
            "TRIAGE_ADAPTATEUR est vide. Déployez avec "
            "TRIAGE_ADAPTATEUR=<compte>/<dépôt> pour que l'adaptateur entraîné "
            "soit servi."
        )

    subprocess.Popen(_commande_vllm(adaptateur))
    _attendre_vllm()
    _verifier_adaptateur_servi()


@app.function(
    image=image_api,
    # Presidio et les deux modeles spaCy tiennent dans 2 Go ; un quart de
    # coeur suffit a une API qui attend le GPU la plupart du temps.
    cpu=0.25,
    memory=2048,
    volumes={"/journal": journal},
    secrets=secrets,
    timeout=600,
    scaledown_window=300,
    max_containers=1,
)
@modal.concurrent(max_inputs=8)
@modal.asgi_app()
def service() -> Any:
    """Expose l'API FastAPI ; seule une requete authentifiee atteint le GPU."""
    if not os.environ.get("TRIAGE_CLES_API", "").strip():
        # Sans cle, l'API serait ouverte a tous : un secret recree vide ne doit
        # pas exposer le GPU en silence.
        raise RuntimeError("TRIAGE_CLES_API est vide : le service refuse de démarrer sans clé.")

    url_vllm = vllm_serveur.get_web_url()
    if not url_vllm:
        raise RuntimeError("URL de vllm_serveur introuvable : fonction non déployée.")
    os.environ["VLLM_BASE_URL"] = url_vllm
    os.environ["VLLM_MODELE"] = NOM_SERVI
    os.environ["TRIAGE_JOURNAL"] = "/journal/journal_triage.jsonl"

    from triage.api.app import app as application

    return application


@app.local_entrypoint()
def verifier() -> None:
    """Appelle l'endpoint deploye et affiche le triage obtenu."""
    import httpx

    url = service.get_web_url()
    cle = os.environ.get("TRIAGE_CLE_API", "")
    reponse = httpx.post(
        f"{url}/triage",
        headers={"X-Cle-Api": cle},
        json={
            "langue": "fr",
            "motif": "douleur thoracique",
            "age": 68,
            "sexe": "masculin",
            "signe_gravite": True,
            "constantes": {"saturation": 88, "glasgow": 14, "frequence_cardiaque": 118},
        },
        timeout=300.0,
    )
    reponse.raise_for_status()
    corps = reponse.json()
    print(f"niveau  : {corps['niveau']}")
    print(f"moteur  : {corps['moteur']} ({corps['modele']})")
    print(f"latence : {corps['latence_ms']} ms")
