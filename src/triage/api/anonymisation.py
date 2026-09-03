"""Masquage des identites dans les champs libres du service.

Le meme anonymiseur qu'a l'etape 1, mais charge une seule fois et partage par
toutes les requetes : construire les moteurs Presidio coute plusieurs secondes
et plusieurs centaines de mega-octets, ce qui serait redhibitoire par appel.

Il ne s'agit pas de rejouer l'anonymisation du corpus : ici la cible est
etroite -- le nom qu'un agent d'accueil aura saisi dans un champ clinique.
"""

from __future__ import annotations

import functools
import os
from typing import Final

from triage.data.anonymize import Anonymiseur

# Le masquage peut etre coupe en environnement de test, ou l'interet est de
# verifier la logique de triage sans payer le chargement des modeles spaCy.
VARIABLE_DESACTIVATION: Final[str] = "TRIAGE_SANS_ANONYMISATION"


@functools.lru_cache(maxsize=1)
def anonymiseur() -> Anonymiseur:
    """Instance unique, construite au premier appel seulement."""
    return Anonymiseur()


def masquage_actif() -> bool:
    return os.environ.get(VARIABLE_DESACTIVATION, "").strip().lower() not in {
        "1",
        "true",
        "oui",
    }


def masquer(texte: str, langue: str = "fr") -> str:
    """Remplace les identites directes par des marqueurs types."""
    if not texte or not texte.strip() or not masquage_actif():
        return texte
    return anonymiseur().anonymiser(texte, langue=langue).texte
