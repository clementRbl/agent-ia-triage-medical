"""Controle qualite du masquage.

Exigence de l'etape 1 : "Controlez la qualite du masquage pour vous assurer
qu'aucune donnee personnelle identifiable ne subsiste."

Principe : on anonymise, puis on **re-analyse la sortie**. Toute entite
identifiante encore detectee dans le texte anonymise est un residu, et le
rapport en donne le compte, le taux et des exemples.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from triage.data.anonymize import Anonymiseur

# Entites dont la presence residuelle est un echec de masquage.
ENTITES_IDENTIFIANTES: tuple[str, ...] = (
    "PERSON",
    "FR_CIVILITE",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "FR_NIR",
    "IBAN_CODE",
)


@dataclass
class RapportQC:
    nb_textes: int = 0
    nb_textes_avec_pii: int = 0
    entites_retirees: dict[str, int] = field(default_factory=dict)
    residus: dict[str, int] = field(default_factory=dict)
    exemples_residus: list[dict[str, str]] = field(default_factory=list)

    @property
    def taux_residuel(self) -> float:
        """Part des textes contenant encore une entite identifiante."""
        return len(self.exemples_residus) / self.nb_textes if self.nb_textes else 0.0

    def ecrire(self, chemin: Path) -> Path:
        chemin.parent.mkdir(parents=True, exist_ok=True)
        charge = {
            "nb_textes": self.nb_textes,
            "nb_textes_avec_pii": self.nb_textes_avec_pii,
            "entites_retirees": self.entites_retirees,
            "residus": self.residus,
            "taux_residuel": round(self.taux_residuel, 5),
            "exemples_residus": self.exemples_residus[:20],
        }
        chemin.write_text(json.dumps(charge, ensure_ascii=False, indent=2), encoding="utf-8")
        return chemin


def controler(
    textes: list[str],
    anonymiseur: Anonymiseur | None = None,
    langue: str = "fr",
    max_exemples: int = 20,
) -> RapportQC:
    """Anonymise puis re-analyse chaque texte pour detecter les residus."""
    anonymiseur = anonymiseur or Anonymiseur()
    rapport = RapportQC(nb_textes=len(textes))

    for texte in textes:
        resultat = anonymiseur.anonymiser(texte, langue=langue)
        if resultat.nb_entites:
            rapport.nb_textes_avec_pii += 1
        for entite, n in resultat.entites.items():
            rapport.entites_retirees[entite] = rapport.entites_retirees.get(entite, 0) + n

        # Deuxieme passe : que reste-t-il dans la sortie ?
        restants = anonymiseur.analyser(
            resultat.texte, langue=langue, entites=ENTITES_IDENTIFIANTES
        )
        if not restants:
            continue
        for r in restants:
            rapport.residus[r.entity_type] = rapport.residus.get(r.entity_type, 0) + 1
        if len(rapport.exemples_residus) < max_exemples:
            r = restants[0]
            rapport.exemples_residus.append(
                {
                    "entite": r.entity_type,
                    "extrait": resultat.texte[max(0, r.start - 60) : r.end + 60],
                    "detecte": resultat.texte[r.start : r.end],
                }
            )
    return rapport
