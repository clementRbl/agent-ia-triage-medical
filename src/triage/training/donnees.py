"""Chargement des jeux produits en semaine 1 vers le format attendu par TRL."""

from __future__ import annotations

from pathlib import Path

import datasets
import pandas as pd

TRAITE = Path("data/processed")


def _lire(fichier: str, split: str, dossier: Path) -> pd.DataFrame:
    chemin = dossier / fichier
    if not chemin.exists():
        raise FileNotFoundError(
            f"{chemin} absent. Construisez d'abord les jeux : "
            'uv run python -c "from triage.data.build import construire_sft; construire_sft()"'
        )
    donnees = pd.read_parquet(chemin)
    partie = donnees[donnees["split"] == split]
    if partie.empty:
        raise ValueError(f"Split {split!r} vide dans {chemin}")
    return partie


def charger_sft(split: str, dossier: Path = TRAITE, limite: int | None = None) -> datasets.Dataset:
    """Jeu SFT au format conversationnel `messages`.

    On ne conserve que la conversation : les metadonnees restent dans le
    parquet, ou elles servent a l'analyse, pas a l'entrainement.
    """
    partie = _lire("sft.parquet", split, dossier)
    if limite:
        partie = partie.head(limite)
    return datasets.Dataset.from_list(
        [
            {
                "messages": [
                    {"role": "user", "content": ligne["instruction"]},
                    {"role": "assistant", "content": ligne["reponse"]},
                ]
            }
            for ligne in partie.to_dict(orient="records")
        ]
    )


def charger_dpo(split: str, dossier: Path = TRAITE, limite: int | None = None) -> datasets.Dataset:
    """Jeu de preferences au format conversationnel attendu par DPOTrainer."""
    partie = _lire("dpo.parquet", split, dossier)
    if limite:
        partie = partie.head(limite)
    return datasets.Dataset.from_list(
        [
            {
                "prompt": [{"role": "user", "content": ligne["prompt"]}],
                "chosen": [{"role": "assistant", "content": ligne["chosen"]}],
                "rejected": [{"role": "assistant", "content": ligne["rejected"]}],
            }
            for ligne in partie.to_dict(orient="records")
        ]
    )
