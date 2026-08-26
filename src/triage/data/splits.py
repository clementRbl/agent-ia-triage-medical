"""Decoupage train / validation / test sans fuite.

Point de vigilance du cahier des charges : "ne pas melanger donnees
d'entrainement et donnees d'evaluation".

Le piege propre a ce corpus : dans MediQAl, plusieurs questions portent sur le
**meme cas clinique** (4 969 questions pour 1 011 cas). Un decoupage ligne a
ligne placerait le meme cas des deux cotes de la frontiere et surestimerait les
performances. On decoupe donc par groupe.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Final

import pandas as pd

PROPORTIONS_DEFAUT: Final[dict[str, float]] = {"train": 0.8, "validation": 0.1, "test": 0.1}


def _empreinte_groupe(valeur: object, graine: int) -> int:
    """Affectation deterministe et stable : ne depend ni de l'ordre ni du volume.

    Reproductible d'une execution a l'autre, et un nouvel enregistrement
    n'entraine pas la redistribution des precedents.
    """
    brut = f"{graine}:{valeur}".encode()
    return int.from_bytes(hashlib.sha256(brut).digest()[:8], "big")


def repartir_par_groupe(
    donnees: pd.DataFrame,
    colonne_groupe: str,
    proportions: dict[str, float] | None = None,
    graine: int = 42,
) -> pd.Series:
    """Retourne la colonne de split, en gardant chaque groupe entier d'un cote.

    Les lignes sans valeur de groupe sont traitees comme des groupes distincts :
    elles ne peuvent donc pas fuiter.
    """
    proportions = proportions or PROPORTIONS_DEFAUT
    total = sum(proportions.values())
    if abs(total - 1.0) > 1e-6:
        raise ValueError(f"Les proportions doivent sommer à 1, obtenu {total}")
    if colonne_groupe not in donnees.columns:
        raise KeyError(f"Colonne de groupe absente : {colonne_groupe!r}")

    noms = list(proportions)
    seuils: list[tuple[str, float]] = []
    cumul = 0.0
    for nom in noms:
        cumul += proportions[nom]
        seuils.append((nom, cumul))

    groupes = donnees[colonne_groupe].where(
        donnees[colonne_groupe].notna(),
        pd.Series([f"__vide__{i}" for i in range(len(donnees))], index=donnees.index),
    )

    def _affecter(groupe: object) -> str:
        position = (_empreinte_groupe(groupe, graine) % 10_000) / 10_000
        for nom, seuil in seuils:
            if position < seuil:
                return nom
        return noms[-1]

    return groupes.map(_affecter).rename("split")


@dataclass(frozen=True)
class Fuite:
    """Un groupe present dans plusieurs splits."""

    groupe: str
    splits: tuple[str, ...]
    nb_lignes: int


def detecter_fuites(
    donnees: pd.DataFrame, colonne_groupe: str, colonne_split: str = "split"
) -> list[Fuite]:
    """Liste les groupes qui apparaissent dans plus d'un split."""
    for colonne in (colonne_groupe, colonne_split):
        if colonne not in donnees.columns:
            raise KeyError(f"Colonne absente : {colonne!r}")

    par_groupe = donnees.groupby(colonne_groupe, dropna=True)[colonne_split]
    fuites: list[Fuite] = []
    for groupe, splits in par_groupe:
        distincts = tuple(sorted(set(splits)))
        if len(distincts) > 1:
            fuites.append(Fuite(groupe=str(groupe), splits=distincts, nb_lignes=len(splits)))
    return fuites


def verifier_absence_fuite(
    donnees: pd.DataFrame, colonne_groupe: str, colonne_split: str = "split"
) -> None:
    """Leve une exception si un groupe est reparti sur plusieurs splits."""
    fuites = detecter_fuites(donnees, colonne_groupe, colonne_split)
    if not fuites:
        return
    apercu = "\n".join(
        f"  - {f.groupe[:70]!r} présent dans {f.splits} ({f.nb_lignes} lignes)" for f in fuites[:10]
    )
    raise ValueError(
        f"Fuite entre les jeux : {len(fuites)} groupe(s) réparti(s) sur plusieurs splits.\n{apercu}"
    )
