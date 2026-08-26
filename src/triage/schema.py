"""Schema des enregistrements du jeu de donnees.

Materialise le schema de metadonnees decrit dans docs/03-etape-1-donnees.md :
symptomes, antecedents, constantes, source, niveau de confiance. Tout
enregistrement, quel que soit son bloc d'origine, respecte ce schema unique.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class Langue(StrEnum):
    FR = "fr"
    EN = "en"


class NiveauPriorite(StrEnum):
    """Les trois niveaux demandes par le CHSA.

    Correspondance avec l'echelle de tri francaise FRENCH (5 niveaux) :
      MAXIMALE -> tri 1-2 (prise en charge immediate ou < 20 min)
      MODEREE  -> tri 3   (prise en charge < 60 min)
      DIFFEREE -> tri 4-5 (prise en charge differee, orientation possible)
    """

    MAXIMALE = "maximale"
    MODEREE = "moderee"
    DIFFEREE = "differee"


class Bloc(StrEnum):
    """Origine fonctionnelle de l'enregistrement (cf. docs/03c)."""

    RAISONNEMENT_CLINIQUE = "A_raisonnement_clinique"
    CONNAISSANCE_MEDICALE = "B_connaissance_medicale"
    SOCLE_ANGLOPHONE = "C_socle_anglophone"
    TRIAGE_STRUCTURE = "D_triage_structure"


@dataclass
class Constantes:
    """Constantes vitales. Toutes optionnelles : rarement toutes relevees."""

    frequence_cardiaque: int | None = None  # bpm
    pression_systolique: int | None = None  # mmHg
    pression_diastolique: int | None = None  # mmHg
    frequence_respiratoire: int | None = None  # /min
    saturation: int | None = None  # SpO2, %
    temperature: float | None = None  # °C
    glasgow: int | None = None  # 3-15
    douleur: int | None = None  # EVA 0-10

    def est_vide(self) -> bool:
        return all(v is None for v in asdict(self).values())


@dataclass
class Enregistrement:
    """Une paire instruction-reponse et sa tracabilite."""

    id: str
    langue: Langue
    instruction: str
    reponse: str
    bloc: Bloc
    source: str
    source_id: str
    licence: str

    symptomes: list[str] = field(default_factory=list)
    antecedents: list[str] = field(default_factory=list)
    constantes: Constantes = field(default_factory=Constantes)
    niveau_priorite: NiveauPriorite | None = None

    # Tracabilite
    niveau_confiance: float = 1.0
    anonymise: bool = False
    transformations: list[str] = field(default_factory=list)
    groupe: str = ""  # cle de decoupage : jamais eclatee entre deux splits
    split: str | None = None

    def __post_init__(self) -> None:
        if not self.instruction.strip():
            raise ValueError(f"{self.id} : instruction vide")
        if not self.reponse.strip():
            raise ValueError(f"{self.id} : réponse vide")
        if not 0.0 <= self.niveau_confiance <= 1.0:
            raise ValueError(f"{self.id} : niveau de confiance hors bornes")
        if not self.groupe:
            self.groupe = self.source_id

    def en_dict(self) -> dict[str, Any]:
        """Forme plate, prete pour parquet ou JSONL."""
        donnees = asdict(self)
        constantes = donnees.pop("constantes")
        donnees["constantes"] = {k: v for k, v in constantes.items() if v is not None}
        return donnees

    def en_exemple_sft(self) -> dict[str, str]:
        """Format conversationnel attendu par TRL (SFTTrainer)."""
        return {
            "messages": [
                {"role": "user", "content": self.instruction},
                {"role": "assistant", "content": self.reponse},
            ]
        }


@dataclass
class PairePreference:
    """Paire chosen/rejected pour l'alignement DPO."""

    id: str
    langue: Langue
    prompt: str
    chosen: str
    rejected: str
    source: str
    source_id: str
    licence: str
    type_preference: str = ""  # label_type d'origine : human, hard, easy, length
    motif_rejet: str = ""  # ce que la reponse rejetee illustre
    groupe: str = ""
    split: str | None = None

    def __post_init__(self) -> None:
        if self.chosen.strip() == self.rejected.strip():
            raise ValueError(f"{self.id} : chosen et rejected identiques")
        for nom, valeur in (("prompt", self.prompt), ("chosen", self.chosen)):
            if not valeur.strip():
                raise ValueError(f"{self.id} : {nom} vide")
        if not self.groupe:
            self.groupe = self.source_id

    def en_dict(self) -> dict[str, Any]:
        return asdict(self)
