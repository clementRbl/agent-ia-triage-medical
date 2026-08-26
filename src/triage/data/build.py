"""Assemblage du jeu SFT bilingue et du jeu de preferences DPO.

Composition retenue (docs/03c-plan-composition-dataset.md) :

  A  raisonnement clinique   MediQAl oeq          fr   2 000
  B  connaissance medicale   MediQAl mcqu + mcqm  fr   1 000
  C  socle anglophone        UltraMedical chosen  en   1 000
  D  triage structure        regles explicites    fr+en 1 000

Deux garde-fous traversent tout le module :
  - le decoupage se fait par **groupe** (cas clinique, prompt d'origine), jamais
    ligne a ligne, sinon un meme cas se retrouve des deux cotes de la frontiere ;
  - les prompts d'UltraMedical sont repartis en trois viviers disjoints
    (SFT / DPO / evaluation) : un prompt vu a l'entrainement ne peut pas
    reapparaitre a l'evaluation.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Final

import pandas as pd

from triage.audit import Manifeste
from triage.data.anonymize import Anonymiseur
from triage.data.splits import repartir_par_groupe, verifier_absence_fuite
from triage.data.triage import generer_cas, rediger_reponse
from triage.schema import Bloc, Enregistrement, Langue, NiveauPriorite, PairePreference

BRUT = Path("data/raw")
TRAITE = Path("data/processed")

LICENCE_MEDIQAL: Final[str] = "CC-BY-4.0"
LICENCE_ULTRAMEDICAL: Final[str] = "MIT"

# Repartition des prompts UltraMedical en viviers disjoints.
VIVIERS: Final[dict[str, float]] = {"sft": 0.35, "dpo": 0.5, "eval": 0.15}


def _vivier(prompt_id: str, graine: int = 2026) -> str:
    """Affecte un prompt a un vivier, de maniere deterministe et stable."""
    empreinte = hashlib.sha256(f"{graine}:{prompt_id}".encode()).digest()[:8]
    position = (int.from_bytes(empreinte, "big") % 10_000) / 10_000
    cumul = 0.0
    for nom, part in VIVIERS.items():
        cumul += part
        if position < cumul:
            return nom
    return "eval"


def lire_json_array(chemin: Path) -> Iterator[dict[str, Any]]:
    """Parcourt un tableau JSON sans le charger entierement en memoire.

    Le fichier d'entrainement d'UltraMedical pese 948 Mo : un `json.load` le
    triplerait en memoire pour n'en garder qu'une fraction.
    """
    decodeur = json.JSONDecoder()
    tampon = ""
    with chemin.open(encoding="utf-8") as flux:
        # On saute le crochet ouvrant.
        while (caractere := flux.read(1)) and caractere != "[":
            continue
        while True:
            tampon = tampon.lstrip(" \n\r\t,")
            if tampon.startswith("]"):
                return
            try:
                objet, fin = decodeur.raw_decode(tampon)
            except ValueError:
                morceau = flux.read(1 << 20)
                if not morceau:
                    return
                tampon += morceau
                continue
            yield objet
            tampon = tampon[fin:]


# --- Bloc A : raisonnement clinique francais ------------------------------


def bloc_a_raisonnement_clinique(nombre: int) -> list[Enregistrement]:
    donnees = pd.read_parquet(BRUT / "mediqal__oeq__test.parquet")
    donnees = donnees.dropna(subset=["clinical_case", "question", "answer"])
    # On limite a quelques questions par cas : sinon un meme cas clinique
    # occupe une part disproportionnee du bloc.
    donnees = donnees.groupby("clinical_case", group_keys=False).head(3).head(nombre)

    # `to_dict` plutot que `itertuples` : les attributs d'un namedtuple pandas
    # sont construits a l'execution, donc invisibles pour le verificateur de
    # types. L'acces par cle est verifiable et le cout est negligeable ici.
    return [
        Enregistrement(
            id=f"mediqal_oeq_{ligne['id']}",
            langue=Langue.FR,
            instruction=(
                f"Cas clinique :\n{ligne['clinical_case'].strip()}\n\n"
                f"Question : {ligne['question'].strip()}"
            ),
            reponse=ligne["answer"].strip(),
            bloc=Bloc.RAISONNEMENT_CLINIQUE,
            source="MediQAl/oeq",
            source_id=str(ligne["id"]),
            licence=LICENCE_MEDIQAL,
            niveau_confiance=1.0,
            transformations=["mise_en_forme_instruction"],
            groupe=hashlib.sha256(ligne["clinical_case"].encode()).hexdigest()[:16],
        )
        for ligne in donnees.to_dict(orient="records")
    ]


# --- Bloc B : connaissance medicale francaise -----------------------------

_LETTRES: Final[tuple[str, ...]] = ("a", "b", "c", "d", "e")


def bloc_b_connaissance_medicale(nombre: int) -> list[Enregistrement]:
    morceaux = [
        pd.read_parquet(BRUT / f"mediqal__{config}__train.parquet").assign(config=config)
        for config in ("mcqu", "mcqm")
    ]
    donnees = pd.concat(morceaux, ignore_index=True)
    donnees = donnees.dropna(subset=["question", "correct_answers"])
    # Priorite aux QCM adosses a un cas clinique : plus proches d'une situation reelle.
    donnees = donnees.assign(
        _avec_cas=donnees.clinical_case.fillna("").str.strip().ne("")
    ).sort_values("_avec_cas", ascending=False)
    donnees = donnees.head(nombre)

    enregistrements = []
    for ligne in donnees.to_dict(orient="records"):
        propositions = {
            lettre.upper(): ligne[f"answer_{lettre}"]
            for lettre in _LETTRES
            if ligne.get(f"answer_{lettre}")
        }
        correctes = [c for c in str(ligne["correct_answers"]).upper() if c in propositions]
        if not correctes:
            continue

        cas = (ligne["clinical_case"] or "").strip()
        entete = f"Cas clinique :\n{cas}\n\n" if cas else ""
        liste = "\n".join(f"{lettre}. {texte}" for lettre, texte in propositions.items())
        detail = "\n".join(f"{lettre}. {propositions[lettre]}" for lettre in correctes)

        enregistrements.append(
            Enregistrement(
                id=f"mediqal_{ligne['config']}_{ligne['id']}",
                langue=Langue.FR,
                instruction=(
                    f"{entete}Question : {ligne['question'].strip()}\n\n{liste}\n\n"
                    "Indiquez la ou les propositions exactes."
                ),
                reponse=f"Proposition(s) exacte(s) : {', '.join(correctes)}.\n\n{detail}",
                bloc=Bloc.CONNAISSANCE_MEDICALE,
                source=f"MediQAl/{ligne['config']}",
                source_id=str(ligne["id"]),
                licence=LICENCE_MEDIQAL,
                # Le corpus ne fournit pas de justification : la reponse se
                # limite a l'enonce des propositions exactes.
                niveau_confiance=0.9,
                transformations=["qcm_vers_instruction"],
                groupe=hashlib.sha256((cas or str(ligne["question"])).encode()).hexdigest()[:16],
            )
        )
    return enregistrements


# --- Bloc C : socle anglophone --------------------------------------------


def bloc_c_socle_anglophone(
    nombre: int, fichier: str = "ultramedical_train.json"
) -> list[Enregistrement]:
    enregistrements: list[Enregistrement] = []
    for ligne in lire_json_array(BRUT / fichier):
        if len(enregistrements) >= nombre:
            break
        if _vivier(ligne["prompt_id"]) != "sft":
            continue
        reponse = ligne["chosen"][-1]["content"].strip()
        if not reponse or not ligne["prompt"].strip():
            continue
        enregistrements.append(
            Enregistrement(
                id=f"ultramedical_sft_{ligne['prompt_id'].replace(',', '_')}",
                langue=Langue.EN,
                instruction=ligne["prompt"].strip(),
                reponse=reponse,
                bloc=Bloc.SOCLE_ANGLOPHONE,
                source=f"UltraMedical/{ligne['prompt_id'].split(',')[0]}",
                source_id=ligne["prompt_id"],
                licence=LICENCE_ULTRAMEDICAL,
                niveau_confiance=float(ligne["metadata"]["chosen"].get("score", 0)) / 5.0,
                transformations=["extraction_reponse_preferee"],
                groupe=ligne["prompt_id"],
            )
        )
    return enregistrements


# --- Jeu de preferences (DPO) ---------------------------------------------

# Une paire etiquetee "length" a ete departagee sur la longueur de la reponse.
# C'est un biais connu du DPO : le modele apprend a etre bavard, pas juste.
LABELS_EXCLUS: Final[frozenset[str]] = frozenset({"length"})


def construire_dpo(
    nombre: int, fichier: str = "ultramedical_train.json", vivier: str = "dpo"
) -> list[PairePreference]:
    """Extrait des paires chosen/rejected exploitables pour l'alignement."""
    paires: list[PairePreference] = []
    for ligne in lire_json_array(BRUT / fichier):
        if len(paires) >= nombre:
            break
        if ligne["label_type"] in LABELS_EXCLUS or _vivier(ligne["prompt_id"]) != vivier:
            continue
        chosen = ligne["chosen"][-1]["content"].strip()
        rejected = ligne["rejected"][-1]["content"].strip()
        if not chosen or not rejected or chosen == rejected:
            continue
        paires.append(
            PairePreference(
                id=f"dpo_{ligne['prompt_id'].replace(',', '_')}",
                langue=Langue.EN,
                prompt=ligne["prompt"].strip(),
                chosen=chosen,
                rejected=rejected,
                source=f"UltraMedical/{ligne['prompt_id'].split(',')[0]}",
                source_id=ligne["prompt_id"],
                licence=LICENCE_ULTRAMEDICAL,
                type_preference=ligne["label_type"],
                motif_rejet="réponse jugée de moindre qualité par l'annotation source",
                groupe=ligne["prompt_id"],
            )
        )
    return paires


def paires_de_triage(cas: list[Enregistrement]) -> list[PairePreference]:
    """Derive des preferences des cas de triage, en ciblant le sous-triage.

    La reponse rejetee ne se contente pas de changer l'etiquette : elle est
    **coherente avec elle-meme**, ne mentionne aucun critere de gravite et
    minore la priorite. C'est la forme reelle du sous-triage -- les criteres
    n'ont pas ete releves -- et donc un contre-exemple utile. Une reponse qui
    annoncerait un niveau bas tout en listant les criteres de gravite serait
    trop facile a ecarter pour apporter quoi que ce soit a l'alignement.
    """
    minoration = {
        NiveauPriorite.MAXIMALE: NiveauPriorite.MODEREE,
        NiveauPriorite.MODEREE: NiveauPriorite.DIFFEREE,
    }

    paires = []
    for enregistrement in cas:
        niveau = enregistrement.niveau_priorite
        if niveau is None:  # enregistrement hors bloc de triage
            continue
        minore = minoration.get(niveau)
        if minore is None:  # un cas deja differe ne peut pas etre sous-trie
            continue
        rejetee = rediger_reponse(
            minore, [], enregistrement.constantes, enregistrement.langue.value
        )
        paires.append(
            PairePreference(
                id=f"dpo_{enregistrement.id}",
                langue=enregistrement.langue,
                prompt=enregistrement.instruction,
                chosen=enregistrement.reponse,
                rejected=rejetee,
                source="triage_regles",
                source_id=enregistrement.source_id,
                licence="construit (règles explicites)",
                type_preference="sous_triage",
                motif_rejet=(
                    f"sous-triage : {niveau.value} minoré en "
                    f"{minore.value}, critères de gravité non relevés"
                ),
                groupe=enregistrement.groupe,
            )
        )
    return paires


# --- Orchestration --------------------------------------------------------


def _anonymiser(enregistrements: list[Enregistrement], anonymiseur: Anonymiseur) -> dict[str, int]:
    """Anonymise en place et retourne le compte d'entites retirees."""
    total: dict[str, int] = {}
    for enregistrement in enregistrements:
        for champ in ("instruction", "reponse"):
            resultat = anonymiseur.anonymiser(
                getattr(enregistrement, champ), langue=enregistrement.langue.value
            )
            setattr(enregistrement, champ, resultat.texte)
            for entite, n in resultat.entites.items():
                total[entite] = total.get(entite, 0) + n
        enregistrement.anonymise = True
        enregistrement.transformations.append("anonymisation_presidio")
    return total


def construire_sft(
    volumes: dict[str, int] | None = None,
    graine: int = 42,
    dossier: Path = TRAITE,
) -> pd.DataFrame:
    """Construit le jeu SFT complet : blocs, anonymisation, decoupage, manifeste."""
    volumes = volumes or {"A": 2000, "B": 1000, "C": 1000, "D": 1000}
    dossier.mkdir(parents=True, exist_ok=True)

    enregistrements = (
        bloc_a_raisonnement_clinique(volumes["A"])
        + bloc_b_connaissance_medicale(volumes["B"])
        + bloc_c_socle_anglophone(volumes["C"])
        + generer_cas(volumes["D"], graine=graine)
    )

    # Les cas construits ne contiennent aucun patient reel : on n'anonymise que
    # ce qui provient d'un corpus.
    a_anonymiser = [e for e in enregistrements if e.bloc is not Bloc.TRIAGE_STRUCTURE]
    entites = _anonymiser(a_anonymiser, Anonymiseur())

    donnees = pd.DataFrame([e.en_dict() for e in enregistrements])
    donnees["split"] = repartir_par_groupe(donnees, "groupe", graine=graine)
    verifier_absence_fuite(donnees, "groupe")

    chemin = dossier / "sft.parquet"
    donnees.to_parquet(chemin, index=False)

    manifeste = Manifeste(
        etape="construction_sft",
        parametres={"volumes": volumes, "graine": graine, "viviers": VIVIERS},
        statistiques={
            "par_bloc": donnees.bloc.value_counts().to_dict(),
            "par_langue": donnees.langue.value_counts().to_dict(),
            "par_split": donnees.split.value_counts().to_dict(),
            "entites_anonymisees": entites,
            "textes_anonymises": len(a_anonymiser),
        },
    )
    manifeste.ajouter_fichier(chemin, entree=False, nb_lignes=len(donnees))
    manifeste.ecrire()
    return donnees


def construire_jeu_dpo(
    nombre_ultramedical: int = 2000,
    nombre_triage: int = 1000,
    graine: int = 42,
    dossier: Path = TRAITE,
) -> pd.DataFrame:
    """Construit le jeu de preferences : UltraMedical + paires de sous-triage."""
    dossier.mkdir(parents=True, exist_ok=True)

    paires = construire_dpo(nombre_ultramedical) + paires_de_triage(
        generer_cas(nombre_triage, graine=graine)
    )
    donnees = pd.DataFrame([p.en_dict() for p in paires])
    donnees["split"] = repartir_par_groupe(donnees, "groupe", graine=graine)
    verifier_absence_fuite(donnees, "groupe")

    chemin = dossier / "dpo.parquet"
    donnees.to_parquet(chemin, index=False)

    manifeste = Manifeste(
        etape="construction_dpo",
        parametres={
            "nombre_ultramedical": nombre_ultramedical,
            "nombre_triage": nombre_triage,
            "labels_exclus": sorted(LABELS_EXCLUS),
            "graine": graine,
        },
        statistiques={
            "par_source": donnees.source.str.split("/").str[0].value_counts().to_dict(),
            "par_type_preference": donnees.type_preference.value_counts().to_dict(),
            "par_split": donnees.split.value_counts().to_dict(),
        },
    )
    manifeste.ajouter_fichier(chemin, entree=False, nb_lignes=len(donnees))
    manifeste.ecrire()
    return donnees


# --- Export -----------------------------------------------------------------


def exporter_jsonl(dossier: Path = TRAITE) -> dict[str, Path]:
    """Ecrit les jeux au format JSONL, un fichier par split et par jeu.

    Format directement consommable par TRL :
      - SFT : `messages`, conversation utilisateur/assistant ;
      - DPO : `prompt`, `chosen`, `rejected`.
    Les metadonnees accompagnent chaque ligne pour rester auditables.
    """
    ecrits: dict[str, Path] = {}
    manifeste = Manifeste(etape="export_jsonl")

    for jeu in ("sft", "dpo"):
        source = dossier / f"{jeu}.parquet"
        if not source.exists():
            continue
        manifeste.ajouter_fichier(source, entree=True)
        donnees = pd.read_parquet(source)

        for split in sorted(donnees["split"].unique()):
            partie = donnees[donnees["split"] == split]
            cible = dossier / "jsonl" / f"{jeu}_{split}.jsonl"
            cible.parent.mkdir(parents=True, exist_ok=True)

            with cible.open("w", encoding="utf-8") as flux:
                for ligne in partie.to_dict(orient="records"):
                    charge: dict[str, Any]
                    if jeu == "sft":
                        charge = {
                            "messages": [
                                {"role": "user", "content": ligne["instruction"]},
                                {"role": "assistant", "content": ligne["reponse"]},
                            ]
                        }
                    else:
                        charge = {
                            "prompt": ligne["prompt"],
                            "chosen": ligne["chosen"],
                            "rejected": ligne["rejected"],
                        }
                    charge["metadonnees"] = {
                        cle: valeur
                        for cle, valeur in ligne.items()
                        if cle not in {"instruction", "reponse", "prompt", "chosen", "rejected"}
                    }
                    flux.write(json.dumps(charge, ensure_ascii=False, default=str) + "\n")

            manifeste.ajouter_fichier(cible, entree=False, nb_lignes=len(partie))
            ecrits[f"{jeu}/{split}"] = cible

    manifeste.ecrire()
    return ecrits
