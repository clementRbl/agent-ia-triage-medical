"""Contrats d'entree et de sortie de l'API.

Types explicites plutot que dictionnaires libres : le SIH du CHSA doit pouvoir
generer un client a partir du schema OpenAPI, et une valeur hors bornes doit
etre refusee au bord du service, pas decouverte au milieu du bareme.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from triage.api.questionnaire import TypeReponse
from triage.schema import Langue, NiveauPriorite


class ConstantesEntree(BaseModel):
    """Constantes vitales, toutes optionnelles et toutes bornees.

    Les bornes sont physiologiques : une SpO2 a 150 % est une erreur de saisie,
    et la laisser passer produirait un triage rassurant sur une valeur absurde.
    """

    # Un exemple rempli plutot qu'un gabarit vide : la documentation interactive
    # devient utilisable sans avoir a deviner ce qu'attend chaque champ.
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "frequence_cardiaque": 118,
                "pression_systolique": 88,
                "pression_diastolique": 55,
                "frequence_respiratoire": 32,
                "saturation": 88,
                "temperature": 37.4,
                "glasgow": 14,
                "douleur": 8,
            }
        }
    )

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

    langue: Annotated[
        Langue,
        Field(default=Langue.FR, description="Langue des questions et de la réponse rendue."),
    ]

    model_config = ConfigDict(json_schema_extra={"example": {"langue": "fr"}})


class ReponseSoumise(BaseModel):
    """Reponse a la question courante."""

    cle: Annotated[
        str,
        Field(
            min_length=1,
            max_length=64,
            description="Reprendre telle quelle la clé de la question précédemment renvoyée.",
        ),
    ]
    valeur: Annotated[
        str,
        Field(
            min_length=1,
            max_length=500,
            description="Toujours une chaîne, même pour un nombre : « 87 », « oui », « 37,5 ».",
        ),
    ]

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"summary": "Motif de recours", "value": {"cle": "motif", "valeur": "dyspnée"}},
                {"summary": "Âge", "value": {"cle": "age", "valeur": "72"}},
                {
                    "summary": "Dépistage des signes de gravité",
                    "value": {"cle": "signe_gravite", "valeur": "non"},
                },
                {"summary": "Saturation", "value": {"cle": "saturation", "valeur": "87"}},
            ]
        }
    )


class QuestionSortie(BaseModel):
    """Question a poser, telle que le client doit l'afficher."""

    cle: str
    libelle: str
    type_reponse: TypeReponse
    minimum: float | None = None
    maximum: float | None = None
    unite: str | None = None
    options: list[str] = Field(default_factory=list)
    aide: Annotated[
        str | None,
        Field(
            default=None,
            description=(
                "Mode d'emploi de la mesure, à afficher avec la question. "
                "Peut contenir des retours à la ligne."
            ),
        ),
    ]


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
    motif: Annotated[
        str,
        Field(min_length=2, max_length=300, description="Motif de recours, en texte libre."),
    ]
    age: Annotated[int | None, Field(default=None, ge=0, le=120, description="Âge en années.")]
    sexe: Annotated[
        str | None,
        Field(
            default=None,
            max_length=20,
            description="« masculin » / « féminin » ou l'équivalent anglais.",
        ),
    ]
    signe_gravite: Annotated[
        bool,
        Field(
            default=False,
            description="Vrai si un signe de gravité lié au motif est présent. "
            "À lui seul, il place le cas en urgence maximale.",
        ),
    ]
    antecedents: Annotated[list[str], Field(default_factory=list, max_length=20)]
    constantes: ConstantesEntree = Field(default_factory=ConstantesEntree)

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "summary": "Urgence maximale — douleur thoracique",
                    "description": "SpO2 basse, pression effondrée et signe de gravité.",
                    "value": {
                        "langue": "fr",
                        "motif": "douleur thoracique",
                        "age": 68,
                        "sexe": "masculin",
                        "signe_gravite": True,
                        "antecedents": ["hypertension artérielle", "tabagisme"],
                        "constantes": {
                            "frequence_cardiaque": 118,
                            "pression_systolique": 88,
                            "pression_diastolique": 55,
                            "frequence_respiratoire": 32,
                            "saturation": 88,
                            "temperature": 37.4,
                            "glasgow": 14,
                            "douleur": 8,
                        },
                    },
                },
                {
                    "summary": "Urgence modérée — douleur abdominale fébrile",
                    "description": "Fièvre à 39,1 °C et tachycardie, sans critère majeur.",
                    "value": {
                        "langue": "fr",
                        "motif": "douleur abdominale",
                        "age": 44,
                        "sexe": "féminin",
                        "signe_gravite": False,
                        "antecedents": ["lithiase biliaire"],
                        "constantes": {
                            "frequence_cardiaque": 112,
                            "pression_systolique": 118,
                            "pression_diastolique": 72,
                            "frequence_respiratoire": 22,
                            "saturation": 96,
                            "temperature": 39.1,
                            "glasgow": 15,
                            "douleur": 7,
                        },
                    },
                },
                {
                    "summary": "Prise en charge différée — traumatisme de membre",
                    "description": "Constantes normales, aucun signe de gravité.",
                    "value": {
                        "langue": "fr",
                        "motif": "traumatisme d'un membre",
                        "age": 30,
                        "sexe": "féminin",
                        "signe_gravite": False,
                        "antecedents": [],
                        "constantes": {
                            "frequence_cardiaque": 72,
                            "pression_systolique": 125,
                            "pression_diastolique": 78,
                            "frequence_respiratoire": 15,
                            "saturation": 99,
                            "temperature": 36.8,
                            "glasgow": 15,
                            "douleur": 3,
                        },
                    },
                },
            ]
        }
    )


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
