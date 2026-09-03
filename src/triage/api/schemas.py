"""Contrats d'entree et de sortie de l'API.

Types explicites plutot que dictionnaires libres : le SIH du CHSA doit pouvoir
generer un client a partir du schema OpenAPI, et une valeur hors bornes doit
etre refusee au bord du service, pas decouverte au milieu du bareme.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field

from triage.api.questionnaire import TypeReponse
from triage.schema import Langue, NiveauPriorite


class ConstantesEntree(BaseModel):
    """Constantes vitales, toutes optionnelles et toutes bornees.

    Les bornes sont physiologiques : une SpO2 a 150 % est une erreur de saisie,
    et la laisser passer produirait un triage rassurant sur une valeur absurde.
    """

    frequence_cardiaque: Annotated[int | None, Field(default=None, ge=20, le=220)]
    pression_systolique: Annotated[int | None, Field(default=None, ge=50, le=250)]
    pression_diastolique: Annotated[int | None, Field(default=None, ge=20, le=150)]
    frequence_respiratoire: Annotated[int | None, Field(default=None, ge=4, le=60)]
    saturation: Annotated[int | None, Field(default=None, ge=50, le=100)]
    temperature: Annotated[float | None, Field(default=None, ge=30.0, le=43.0)]
    glasgow: Annotated[int | None, Field(default=None, ge=3, le=15)]
    douleur: Annotated[int | None, Field(default=None, ge=0, le=10)]


class OuvertureEntretien(BaseModel):
    """Demande d'ouverture d'un entretien de triage."""

    langue: Langue = Langue.FR


class ReponseSoumise(BaseModel):
    """Reponse a la question courante."""

    cle: Annotated[str, Field(min_length=1, max_length=64)]
    valeur: Annotated[str, Field(min_length=1, max_length=500)]


class QuestionSortie(BaseModel):
    """Question a poser, telle que le client doit l'afficher."""

    cle: str
    libelle: str
    type_reponse: TypeReponse
    minimum: float | None = None
    maximum: float | None = None
    unite: str | None = None
    options: list[str] = Field(default_factory=list)


class TriageSortie(BaseModel):
    """Evaluation rendue par le service."""

    niveau: NiveauPriorite
    explication: str
    criteres: list[str]
    niveau_modele: NiveauPriorite | None = None
    niveau_regles: NiveauPriorite
    escalade: bool = Field(
        description="Vrai quand le garde-fou a relevé la priorité annoncée par le modèle."
    )
    moteur: str
    modele: str
    latence_ms: float


class EtatEntretien(BaseModel):
    """Reponse standard : soit la question suivante, soit le triage."""

    session: str
    termine: bool
    question: QuestionSortie | None = None
    triage: TriageSortie | None = None
    questions_posees: int


class DemandeTriageDirect(BaseModel):
    """Triage en une passe, pour un SIH qui detient deja le dossier.

    Le questionnaire adaptatif sert l'accueil ; un systeme hospitalier qui a
    deja les constantes n'a pas a le derouler question par question.
    """

    langue: Langue = Langue.FR
    motif: Annotated[str, Field(min_length=2, max_length=300)]
    age: Annotated[int | None, Field(default=None, ge=0, le=120)]
    sexe: Annotated[str | None, Field(default=None, max_length=20)]
    signe_gravite: bool = False
    antecedents: Annotated[list[str], Field(default_factory=list, max_length=20)]
    constantes: ConstantesEntree = Field(default_factory=ConstantesEntree)


class IntegriteJournal(BaseModel):
    """Resultat de la verification du journal d'audit."""

    entrees: int
    intact: bool
    ruptures: list[str] = Field(default_factory=list)


class Version(BaseModel):
    """Identification de la version servie, exigee pour tout audit a posteriori."""

    service: str
    moteur: str
    modele: str
    revision: str | None = None
