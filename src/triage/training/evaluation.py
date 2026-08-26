"""Evaluation clinique du modele sur les cas de triage.

La metrique qui compte n'est pas l'exactitude globale mais le **taux de
sous-triage** : la part des cas ou le modele annonce une priorite plus basse
que la priorite reelle. Un sur-triage encombre le service ; un sous-triage
laisse un patient grave en salle d'attente. Les deux ne se compensent pas et
ne doivent jamais etre agreges dans un seul chiffre.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from triage.schema import NiveauPriorite

# Rang ordonne : c'est lui qui distingue une erreur par exces d'une erreur par
# defaut. Sans ordre, on ne saurait pas de quel cote penche une confusion.
RANG: dict[NiveauPriorite, int] = {
    NiveauPriorite.DIFFEREE: 0,
    NiveauPriorite.MODEREE: 1,
    NiveauPriorite.MAXIMALE: 2,
}

# Libelles produits par le modele, dans les deux langues.
_LIBELLES: dict[str, NiveauPriorite] = {
    "URGENCE MAXIMALE": NiveauPriorite.MAXIMALE,
    "URGENCE MODÉRÉE": NiveauPriorite.MODEREE,
    "URGENCE MODEREE": NiveauPriorite.MODEREE,
    "PRISE EN CHARGE DIFFÉRÉE": NiveauPriorite.DIFFEREE,
    "PRISE EN CHARGE DIFFEREE": NiveauPriorite.DIFFEREE,
    "HIGHEST PRIORITY": NiveauPriorite.MAXIMALE,
    "MODERATE PRIORITY": NiveauPriorite.MODEREE,
    "DEFERRED CARE": NiveauPriorite.DIFFEREE,
}

_MOTIF = re.compile("|".join(re.escape(libelle) for libelle in _LIBELLES), re.IGNORECASE)


def extraire_niveau(texte: str) -> NiveauPriorite | None:
    """Retrouve le niveau annonce, ou None si le modele n'en annonce aucun.

    Une reponse sans niveau identifiable est un echec de format : elle est
    comptee separement plutot que rattachee arbitrairement a une classe.
    """
    correspondance = _MOTIF.search(texte or "")
    if not correspondance:
        return None
    return _LIBELLES[correspondance.group(0).upper()]


@dataclass
class ResultatEvaluation:
    """Metriques de triage d'un modele sur un jeu de cas."""

    nom: str
    total: int = 0
    exacts: int = 0
    sous_triages: int = 0
    sur_triages: int = 0
    sans_niveau: int = 0
    matrice: dict[str, dict[str, int]] = field(default_factory=dict)
    exemples_sous_triage: list[dict[str, Any]] = field(default_factory=list)

    @property
    def exactitude(self) -> float:
        return self.exacts / self.total if self.total else 0.0

    @property
    def taux_sous_triage(self) -> float:
        """La metrique de securite : proportion de cas dont la priorite est minoree."""
        return self.sous_triages / self.total if self.total else 0.0

    @property
    def taux_sur_triage(self) -> float:
        return self.sur_triages / self.total if self.total else 0.0

    @property
    def taux_sans_niveau(self) -> float:
        return self.sans_niveau / self.total if self.total else 0.0

    def en_dict(self) -> dict[str, Any]:
        return {
            "nom": self.nom,
            "total": self.total,
            "exactitude": round(self.exactitude, 4),
            "taux_sous_triage": round(self.taux_sous_triage, 4),
            "taux_sur_triage": round(self.taux_sur_triage, 4),
            "taux_sans_niveau": round(self.taux_sans_niveau, 4),
            "exacts": self.exacts,
            "sous_triages": self.sous_triages,
            "sur_triages": self.sur_triages,
            "sans_niveau": self.sans_niveau,
            "matrice": self.matrice,
        }


def comparer(
    attendus: list[NiveauPriorite],
    predits: list[NiveauPriorite | None],
    nom: str,
    instructions: list[str] | None = None,
    max_exemples: int = 10,
) -> ResultatEvaluation:
    """Confronte predictions et verite terrain, en separant les deux erreurs."""
    if len(attendus) != len(predits):
        raise ValueError(
            f"{len(attendus)} attendus pour {len(predits)} prédits : longueurs incohérentes"
        )

    resultat = ResultatEvaluation(nom=nom, total=len(attendus))
    resultat.matrice = {
        reel.value: {predit.value: 0 for predit in NiveauPriorite} | {"sans_niveau": 0}
        for reel in NiveauPriorite
    }

    for index, (attendu, predit) in enumerate(zip(attendus, predits, strict=True)):
        if predit is None:
            resultat.sans_niveau += 1
            resultat.matrice[attendu.value]["sans_niveau"] += 1
            continue

        resultat.matrice[attendu.value][predit.value] += 1
        if predit is attendu:
            resultat.exacts += 1
        elif RANG[predit] < RANG[attendu]:
            resultat.sous_triages += 1
            if len(resultat.exemples_sous_triage) < max_exemples:
                resultat.exemples_sous_triage.append(
                    {
                        "index": index,
                        "attendu": attendu.value,
                        "predit": predit.value,
                        "instruction": (instructions[index][:400] if instructions else ""),
                    }
                )
        else:
            resultat.sur_triages += 1

    return resultat
