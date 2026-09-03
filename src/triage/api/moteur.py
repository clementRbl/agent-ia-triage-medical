"""Acces au modele de triage : vLLM en service, regles en repli explicite.

Deux implementations derriere une meme interface :

- `MoteurVLLM` interroge un serveur vLLM par son API compatible OpenAI. C'est
  le mode nominal, celui qui est mesure et deploye.
- `MoteurRegles` produit la reponse a partir des seules regles de triage. Il
  existe pour que l'API soit testable sans GPU, en integration continue.

Le repli n'est jamais silencieux : chaque reponse et chaque entree de journal
portent le nom du moteur qui l'a produite. Un service qui repondrait avec les
regles en croyant interroger le modele donnerait des mesures fausses, et en
production ferait passer pour une evaluation par le modele ce qui n'en est
pas une.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Final, Protocol

import httpx

from triage.data.triage import evaluer_priorite, rediger_reponse
from triage.schema import Constantes, Langue

# Le modele ne raisonne pas en chaine de pensee ici : l'entrainement a ete
# conduit avec `enable_thinking=False`, et servir avec un autre reglage
# changerait la distribution des sorties.
OPTIONS_GABARIT: Final[dict[str, bool]] = {"enable_thinking": False}

TOKENS_MAX_DEFAUT: Final[int] = 320
DELAI_DEFAUT: Final[float] = 60.0


@dataclass(frozen=True)
class Generation:
    """Sortie brute du moteur et sa tracabilite."""

    texte: str
    moteur: str
    modele: str
    latence_ms: float


class Moteur(Protocol):
    """Interface minimale attendue par le service."""

    nom: str

    def generer(self, instruction: str, langue: Langue) -> Generation: ...

    def disponible(self) -> bool: ...


@dataclass
class MoteurVLLM:
    """Client du serveur vLLM, via son API compatible OpenAI."""

    base_url: str
    modele: str
    cle_api: str | None = None
    tokens_max: int = TOKENS_MAX_DEFAUT
    delai: float = DELAI_DEFAUT
    nom: str = "vllm"

    def _entetes(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.cle_api}"} if self.cle_api else {}

    def disponible(self) -> bool:
        try:
            reponse = httpx.get(f"{self.base_url}/health", timeout=5.0, headers=self._entetes())
        except httpx.HTTPError:
            return False
        return reponse.status_code == 200

    def generer(self, instruction: str, langue: Langue) -> Generation:
        charge = {
            "model": self.modele,
            "messages": [{"role": "user", "content": instruction}],
            # Temperature nulle : deux triages du meme tableau clinique doivent
            # donner la meme priorite, sinon la tracabilite ne vaut rien.
            "temperature": 0.0,
            "max_tokens": self.tokens_max,
            "chat_template_kwargs": OPTIONS_GABARIT,
        }
        with httpx.Client(timeout=self.delai) as client:
            reponse = client.post(
                f"{self.base_url}/v1/chat/completions",
                json=charge,
                headers=self._entetes(),
            )
            reponse.raise_for_status()
            corps = reponse.json()
        latence = reponse.elapsed.total_seconds() * 1000
        return Generation(
            texte=corps["choices"][0]["message"]["content"].strip(),
            moteur=self.nom,
            modele=self.modele,
            latence_ms=round(latence, 1),
        )


@dataclass
class MoteurRegles:
    """Repli deterministe : la reponse est deduite des seules regles.

    Utile en integration continue et pour les tests de charge de l'API, ou
    faire tourner un modele de 1,7 milliard de parametres n'apporterait rien.
    Jamais un mode de production : il ne sait rien dire hors du bareme.
    """

    nom: str = "regles"
    modele: str = "bareme_french_simplifie"

    def disponible(self) -> bool:
        return True

    def generer(self, instruction: str, langue: Langue) -> Generation:
        from time import perf_counter

        debut = perf_counter()
        constantes, signe = _relire_instruction(instruction, langue)
        niveau, declencheurs = evaluer_priorite(constantes, signe)
        texte = rediger_reponse(niveau, declencheurs, constantes, langue.value)
        return Generation(
            texte=texte,
            moteur=self.nom,
            modele=self.modele,
            latence_ms=round((perf_counter() - debut) * 1000, 1),
        )


def _relire_instruction(instruction: str, langue: Langue) -> tuple[Constantes, bool]:
    """Extrait du prompt ce dont le bareme a besoin.

    Le moteur de repli recoit le meme prompt que le modele : il doit donc en
    relire les constantes plutot que recevoir l'etat de l'entretien, sans quoi
    les deux moteurs ne seraient pas interchangeables.
    """
    import re

    def entier(motif: str) -> int | None:
        trouve = re.search(motif, instruction)
        return int(trouve.group(1)) if trouve else None

    def decimal(motif: str) -> float | None:
        trouve = re.search(motif, instruction)
        return float(trouve.group(1).replace(",", ".")) if trouve else None

    constantes = Constantes(
        frequence_cardiaque=entier(r"(?:FC|HR) (\d+)/min"),
        pression_systolique=entier(r"(?:PA|BP) (\d+)"),
        pression_diastolique=entier(r"(?:PA|BP) \d+/(\d+)"),
        frequence_respiratoire=entier(r"(?:FR|RR) (\d+)/min"),
        saturation=entier(r"SpO2 (\d+)"),
        temperature=decimal(r"(?:T|Temp) (\d+[.,]\d)"),
        glasgow=entier(r"Glasgow (\d+)"),
        douleur=entier(r"(?:EVA|pain) (\d+)/10"),
    )
    intitule = "Symptômes rapportés" if langue is Langue.FR else "Reported symptoms"
    return constantes, intitule in instruction


def moteur_depuis_environnement() -> Moteur:
    """Construit le moteur decrit par les variables d'environnement.

    Le repli par regles doit etre demande explicitement : sans cela, une URL
    vLLM mal renseignee ferait basculer le service en mode degrade sans que
    personne s'en apercoive.
    """
    if os.environ.get("TRIAGE_MOTEUR", "").strip().lower() == "regles":
        return MoteurRegles()
    base_url = os.environ.get("VLLM_BASE_URL", "").rstrip("/")
    if not base_url:
        raise RuntimeError(
            "VLLM_BASE_URL n'est pas définie. Renseignez l'URL du serveur vLLM, "
            "ou demandez explicitement le repli avec TRIAGE_MOTEUR=regles."
        )
    return MoteurVLLM(
        base_url=base_url,
        modele=os.environ.get("VLLM_MODELE", "triage-qwen3-1.7b"),
        cle_api=os.environ.get("VLLM_CLE_API") or None,
    )
