"""Visualisation avant / apres de la chaine d'anonymisation.

Usage :
    uv run python scripts/demo_anonymisation.py            # 3 cas au hasard
    uv run python scripts/demo_anonymisation.py -n 10      # 10 cas
    uv run python scripts/demo_anonymisation.py --diff     # seulement les differences
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

import pandas as pd

from triage.data.anonymize import Anonymiseur

CORPUS = Path("data/raw/mediqal__oeq__test.parquet")
VERT, ROUGE, GRIS, GRAS, FIN = "\033[32m", "\033[31m", "\033[90m", "\033[1m", "\033[0m"


def _surligner(texte: str) -> str:
    """Colore les marqueurs de remplacement pour les reperer d'un coup d'oeil."""
    for marqueur in ("<PATIENT>", "<DATE>", "<NIR>", "<EMAIL>", "<TELEPHONE>", "<ETABLISSEMENT>"):
        texte = texte.replace(marqueur, f"{VERT}{GRAS}{marqueur}{FIN}")
    return texte


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-n", type=int, default=3, help="nombre de cas à afficher")
    parser.add_argument("--seed", type=int, default=0, help="graine de tirage")
    parser.add_argument(
        "--diff", action="store_true", help="n'afficher que les cas effectivement modifiés"
    )
    args = parser.parse_args()

    if not CORPUS.exists():
        print(f"Corpus absent : {CORPUS}\nLancez d'abord :", file=sys.stderr)
        print(
            '  uv run python -c "from triage.data.ingest import telecharger;'
            " telecharger('mediqal')\"",
            file=sys.stderr,
        )
        return 1

    cas = pd.read_parquet(CORPUS).drop_duplicates("clinical_case").clinical_case.dropna().tolist()
    random.Random(args.seed).shuffle(cas)

    anonymiseur = Anonymiseur()
    affiches = 0
    for texte in cas:
        if affiches >= args.n:
            break
        resultat = anonymiseur.anonymiser(texte, langue="fr")
        if args.diff and not resultat.nb_entites:
            continue
        affiches += 1
        print(f"\n{GRAS}{'═' * 78}{FIN}")
        print(f"{GRAS}CAS {affiches}{FIN}  —  entités retirées : {resultat.entites or 'aucune'}")
        print(f"{GRAS}{'═' * 78}{FIN}")
        print(f"{ROUGE}AVANT{FIN}\n{GRIS}{texte.strip()[:900]}{FIN}")
        print(f"\n{VERT}APRÈS{FIN}\n{_surligner(resultat.texte.strip()[:900])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
