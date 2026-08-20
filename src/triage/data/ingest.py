"""Telechargement et normalisation des corpus sources.

Sources retenues (cf. docs/03b-inventaire-sources.md) :
  - ANR-MALADES/MediQAl          (francais, CC-BY-4.0)
  - TsinghuaC3I/UltraMedical-Preference (anglais, MIT)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

import datasets

from triage.audit import Manifeste

BRUT = Path("data/raw")


@dataclass(frozen=True)
class Source:
    """Description d'un corpus source, licence incluse pour la carte de dataset."""

    identifiant: str
    depot: str
    langue: str
    licence: str
    configs: tuple[str, ...]


SOURCES: Final[dict[str, Source]] = {
    "mediqal": Source(
        identifiant="mediqal",
        depot="ANR-MALADES/MediQAl",
        langue="fr",
        licence="CC-BY-4.0",
        configs=("oeq", "mcqu", "mcqm"),
    ),
    "ultramedical": Source(
        identifiant="ultramedical",
        depot="TsinghuaC3I/UltraMedical-Preference",
        langue="en",
        licence="MIT",
        configs=("default",),
    ),
}


def telecharger(nom: str, dossier: Path = BRUT) -> dict[str, Path]:
    """Telecharge un corpus et l'ecrit en parquet, avec manifeste d'audit."""
    if nom not in SOURCES:
        raise KeyError(f"Source inconnue : {nom!r}. Attendu : {sorted(SOURCES)}")
    source = SOURCES[nom]
    dossier.mkdir(parents=True, exist_ok=True)

    manifeste = Manifeste(
        etape=f"ingestion_{nom}",
        parametres={
            "depot": source.depot,
            "langue": source.langue,
            "licence": source.licence,
        },
    )
    manifeste.entrees.append(f"hf://{source.depot}")

    ecrits: dict[str, Path] = {}
    for config in source.configs:
        jeu = datasets.load_dataset(source.depot, config)
        for split, donnees in jeu.items():
            cible = dossier / f"{nom}__{config}__{split}.parquet"
            donnees.to_parquet(cible)
            manifeste.ajouter_fichier(cible, entree=False, nb_lignes=donnees.num_rows)
            ecrits[f"{config}/{split}"] = cible

    manifeste.ecrire()
    return ecrits
