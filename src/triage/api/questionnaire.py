"""Questionnaire adaptatif de recueil des symptomes.

Le CHSA demande un recueil « intelligent adaptatif » : poser la question utile
au vu des reponses deja obtenues, plutot que derouler un formulaire fixe. Aux
urgences, chaque question coutee est du temps pris a un patient qui attend.

Deux principes gouvernent ce module :

1. **L'ordre suit le pouvoir discriminant.** Les questions sont posees dans
   l'ordre ou elles font basculer le niveau de priorite. Un signe de gravite
   tranche a lui seul ; la douleur, jamais.
2. **L'arret est deterministe.** C'est une regle explicite, jamais le modele,
   qui decide qu'on en sait assez. Un modele de langage qui deciderait de son
   propre arret pourrait conclure sur un dossier vide : ce serait la panne la
   plus dangereuse du systeme.

Le modele intervient apres, pour formuler l'evaluation en langage naturel.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final

from triage.data.triage import PRESENTATIONS, composer_instruction, evaluer_priorite
from triage.schema import Constantes, Langue, NiveauPriorite


class TypeReponse(StrEnum):
    """Forme attendue de la reponse, pour que le client sache quoi afficher."""

    TEXTE = "texte"
    OUI_NON = "oui_non"
    ENTIER = "entier"
    DECIMAL = "decimal"
    CHOIX = "choix"


@dataclass(frozen=True)
class Question:
    """Une question du questionnaire et la facon de la valider."""

    cle: str
    libelle: dict[str, str]
    type_reponse: TypeReponse
    minimum: float | None = None
    maximum: float | None = None
    unite: str | None = None
    choix: dict[str, tuple[str, ...]] | None = None

    def options(self, langue: Langue) -> tuple[str, ...]:
        return self.choix[langue.value] if self.choix else ()

    def texte(self, langue: Langue) -> str:
        return self.libelle[langue.value]


# Ordre volontaire : les constantes qui declenchent une urgence maximale
# d'abord. Une SpO2 a 86 % conclut ; une douleur a 3/10 n'exclut rien.
QUESTIONS_CONSTANTES: Final[tuple[Question, ...]] = (
    Question(
        cle="glasgow",
        libelle={
            "fr": "Quel est le score de Glasgow du patient (3 à 15) ?",
            "en": "What is the patient's Glasgow score (3 to 15)?",
        },
        type_reponse=TypeReponse.ENTIER,
        minimum=3,
        maximum=15,
    ),
    Question(
        cle="saturation",
        libelle={
            "fr": "Quelle est la saturation en oxygène (SpO2, en %) ?",
            "en": "What is the oxygen saturation (SpO2, in %)?",
        },
        type_reponse=TypeReponse.ENTIER,
        minimum=50,
        maximum=100,
        unite="%",
    ),
    Question(
        cle="frequence_respiratoire",
        libelle={
            "fr": "Quelle est la fréquence respiratoire (cycles par minute) ?",
            "en": "What is the respiratory rate (breaths per minute)?",
        },
        type_reponse=TypeReponse.ENTIER,
        minimum=4,
        maximum=60,
        unite="/min",
    ),
    Question(
        cle="pression_systolique",
        libelle={
            "fr": "Quelle est la pression artérielle systolique (mmHg) ?",
            "en": "What is the systolic blood pressure (mmHg)?",
        },
        type_reponse=TypeReponse.ENTIER,
        minimum=50,
        maximum=250,
        unite="mmHg",
    ),
    Question(
        cle="frequence_cardiaque",
        libelle={
            "fr": "Quelle est la fréquence cardiaque (battements par minute) ?",
            "en": "What is the heart rate (beats per minute)?",
        },
        type_reponse=TypeReponse.ENTIER,
        minimum=20,
        maximum=220,
        unite="bpm",
    ),
    Question(
        cle="temperature",
        libelle={
            "fr": "Quelle est la température corporelle (°C) ?",
            "en": "What is the body temperature (°C)?",
        },
        type_reponse=TypeReponse.DECIMAL,
        minimum=30.0,
        maximum=43.0,
        unite="°C",
    ),
    Question(
        cle="douleur",
        libelle={
            "fr": "Comment le patient évalue-t-il sa douleur, de 0 à 10 ?",
            "en": "How does the patient rate their pain, from 0 to 10?",
        },
        type_reponse=TypeReponse.ENTIER,
        minimum=0,
        maximum=10,
    ),
)

QUESTION_MOTIF: Final[Question] = Question(
    cle="motif",
    libelle={
        "fr": "Quel est le motif de consultation ?",
        "en": "What brings the patient in today?",
    },
    type_reponse=TypeReponse.TEXTE,
)

QUESTION_AGE: Final[Question] = Question(
    cle="age",
    libelle={"fr": "Quel âge a le patient ?", "en": "How old is the patient?"},
    type_reponse=TypeReponse.ENTIER,
    minimum=0,
    maximum=120,
    unite="ans",
)

QUESTION_SEXE: Final[Question] = Question(
    cle="sexe",
    libelle={"fr": "Quel est le sexe du patient ?", "en": "What is the patient's sex?"},
    type_reponse=TypeReponse.CHOIX,
    choix={"fr": ("masculin", "féminin"), "en": ("male", "female")},
)

QUESTION_ANTECEDENTS: Final[Question] = Question(
    cle="antecedents",
    libelle={
        "fr": "Le patient a-t-il des antécédents médicaux connus ? (sinon, répondre « aucun »)",
        "en": "Does the patient have any known medical history? (otherwise answer “none”)",
    },
    type_reponse=TypeReponse.TEXTE,
)

# Repli quand le motif libre ne correspond a aucune presentation connue : ces
# signes sont transversaux et justifient a eux seuls une prise en charge
# immediate, quel que soit le motif.
SIGNES_GENERAUX: Final[dict[str, tuple[str, ...]]] = {
    "fr": (
        "troubles de la vigilance",
        "difficulté à parler ou à respirer",
        "douleur d'intensité brutale et inhabituelle",
    ),
    "en": (
        "reduced alertness",
        "difficulty speaking or breathing",
        "sudden severe and unusual pain",
    ),
}


def signes_a_rechercher(motif: str, langue: Langue) -> tuple[str, ...]:
    """Signes de gravite a depister, choisis d'apres le motif de recours.

    C'est le premier ressort de l'adaptativite : on ne demande pas la cyanose
    a un patient venu pour une entorse.
    """
    normalise = motif.casefold()
    for presentation in PRESENTATIONS:
        libelles = {presentation.motif[langue.value].casefold()} | {
            mot.casefold() for mot in presentation.motif.values()
        }
        if any(libelle in normalise or normalise in libelle for libelle in libelles):
            return presentation.signes_gravite[langue.value]
    return SIGNES_GENERAUX[langue.value]


def question_signes(motif: str, langue: Langue) -> Question:
    """Construit la question de depistage des signes de gravite."""
    signes = signes_a_rechercher(motif, langue)
    liste = ", ".join(signes)
    libelle = {
        "fr": f"Un de ces signes est-il présent : {liste} ?",
        "en": f"Is any of these signs present: {liste}?",
    }
    return Question(cle="signe_gravite", libelle=libelle, type_reponse=TypeReponse.OUI_NON)


@dataclass
class Entretien:
    """Etat d'un entretien en cours : ce qui a ete demande et obtenu."""

    langue: Langue = Langue.FR
    motif: str | None = None
    age: int | None = None
    sexe: str | None = None
    antecedents: list[str] = field(default_factory=list)
    signe_gravite: bool | None = None
    constantes: Constantes = field(default_factory=Constantes)
    questions_posees: list[str] = field(default_factory=list)

    def _valeur(self, cle: str) -> float | None:
        return getattr(self.constantes, cle, None)

    def declenche_maximale(self) -> bool:
        """Un critere d'urgence maximale est-il deja rempli ?

        Des que la reponse est oui, poursuivre le questionnaire ne peut plus
        changer le niveau : il ne peut que retarder la prise en charge.
        """
        niveau, _ = evaluer_priorite(self.constantes, bool(self.signe_gravite))
        return niveau is NiveauPriorite.MAXIMALE

    def prochaine_question(self) -> Question | None:
        """Question suivante, ou None quand le recueil est suffisant."""
        if self.motif is None:
            return QUESTION_MOTIF
        # L'age et le sexe passent avant le depistage : deux reponses immediates,
        # et le modele n'a jamais vu a l'entrainement de tableau qui en soit prive.
        if self.age is None:
            return QUESTION_AGE
        if self.sexe is None:
            return QUESTION_SEXE
        if self.signe_gravite is None:
            return question_signes(self.motif, self.langue)
        if self.declenche_maximale():
            return None
        for question in QUESTIONS_CONSTANTES:
            if self._valeur(question.cle) is None:
                return question
            if self.declenche_maximale():
                return None
        if not self.antecedents:
            return QUESTION_ANTECEDENTS
        return None

    def est_complet(self) -> bool:
        return self.prochaine_question() is None

    def niveau_regles(self) -> tuple[NiveauPriorite, list[str]]:
        """Niveau deduit des regles explicites, et criteres qui le motivent."""
        niveau, declencheurs = evaluer_priorite(self.constantes, bool(self.signe_gravite))
        return niveau, [c.libelle[self.langue.value] for c in declencheurs]

    def symptomes(self) -> list[str]:
        """Signes rapportes, sous la forme attendue par le prompt d'entrainement."""
        if not self.signe_gravite:
            return []
        return list(signes_a_rechercher(self.motif or "", self.langue))

    def instruction(self) -> str:
        """Prompt soumis au modele, dans le format exact de l'entrainement.

        Passe par `composer_instruction`, la meme fonction que le generateur du
        bloc D : aucune derive de mise en forme n'est possible entre ce qui a
        ete appris et ce qui est servi.
        """
        return composer_instruction(
            langue=self.langue.value,
            age=self.age,
            sexe=self.sexe,
            motif=self.motif or "",
            symptomes=self.symptomes(),
            antecedents=self.antecedents,
            constantes=self.constantes,
        )
