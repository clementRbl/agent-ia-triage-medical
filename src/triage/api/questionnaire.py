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
    aide: dict[str, str] | None = None

    def options(self, langue: Langue) -> tuple[str, ...]:
        return self.choix[langue.value] if self.choix else ()

    def texte(self, langue: Langue) -> str:
        return self.libelle[langue.value]

    def texte_aide(self, langue: Langue) -> str | None:
        """Mode d'emploi de la mesure, ou None quand la question se suffit.

        Une constante mal comprise est saisie de travers, et une saisie de
        travers produit un triage faux sans declencher la moindre erreur : la
        borne accepte la valeur, le bareme la lit telle quelle. L'aide est donc
        un dispositif de securite, pas un confort.
        """
        return self.aide[langue.value] if self.aide else None


# Le score de Glasgow est le seul item du questionnaire qui se *calcule* au lieu
# de se lire sur un appareil. C'est aussi celui dont une erreur coute le plus
# cher : il ouvre la liste des criteres d'urgence maximale. Le detail du calcul
# est donc servi avec la question, plutot que suppose connu.
AIDE_GLASGOW: Final[dict[str, str]] = {
    "fr": """Score de Glasgow = ouverture des yeux + réponse verbale + réponse motrice.
Total de 3 (coma profond) à 15 (parfaitement conscient).

Ouverture des yeux — de 1 à 4
  4  spontanée
  3  à la demande verbale
  2  à la douleur
  1  aucune

Réponse verbale — de 1 à 5
  5  orientée et cohérente
  4  confuse
  3  mots inappropriés
  2  sons incompréhensibles
  1  aucune

Réponse motrice — de 1 à 6
  6  obéit aux ordres
  5  orientée à la douleur
  4  évitement non adapté
  3  flexion (décortication)
  2  extension (décérébration)
  1  aucune

Un patient éveillé, orienté et qui obéit aux ordres a 15 : c'est le cas le plus
fréquent à l'accueil. Le barème ne retient un critère d'urgence maximale qu'en
dessous de 14 — un score de 14 ne déclenche donc rien à lui seul.""",
    "en": """Glasgow score = eye opening + verbal response + motor response.
Total from 3 (deep coma) to 15 (fully alert).

Eye opening — 1 to 4
  4  spontaneous
  3  to speech
  2  to pain
  1  none

Verbal response — 1 to 5
  5  oriented
  4  confused
  3  inappropriate words
  2  incomprehensible sounds
  1  none

Motor response — 1 to 6
  6  obeys commands
  5  localises pain
  4  withdrawal from pain
  3  flexion (decorticate)
  2  extension (decerebrate)
  1  none

An awake, oriented patient who obeys commands scores 15 — the common case at
the front desk. The rule set only flags a maximum-priority criterion below 14,
so a score of 14 triggers nothing on its own.""",
}


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
        aide=AIDE_GLASGOW,
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
        aide={
            "fr": (
                "Mesure à l'oxymètre de pouls, au repos et en air ambiant. "
                "95 à 100 % chez l'adulte sain.\n\n"
                "Le barème retient une urgence maximale sous 90 %, et une urgence "
                "modérée de 90 à 94 %.\n\n"
                "Limite connue : chez un insuffisant respiratoire chronique, la cible "
                "habituelle est plus basse (88 à 92 %). Le barème ne distingue pas ce "
                "cas et classera donc en urgence modérée une saturation qui, pour ce "
                "patient-là, est sa valeur de base. Il sur-trie volontairement."
            ),
            "en": (
                "Pulse oximeter reading, at rest and on room air. "
                "95 to 100% in a healthy adult.\n\n"
                "The rule set flags maximum priority below 90%, and moderate priority "
                "from 90 to 94%.\n\n"
                "Known limitation: in chronic respiratory failure the usual target is "
                "lower (88 to 92%). The rule set does not tell that case apart and will "
                "therefore rate as moderate a saturation that is this patient's "
                "baseline. It over-triages on purpose."
            ),
        },
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
        aide={
            "fr": (
                "Nombre de cycles respiratoires comptés sur une minute, patient au "
                "repos. 12 à 20 chez l'adulte.\n\n"
                "À ne pas confondre avec le pouls : 60 saisi ici décrit une détresse "
                "respiratoire majeure, pas un cœur normal."
            ),
            "en": (
                "Breaths counted over one minute, patient at rest. "
                "12 to 20 in an adult.\n\n"
                "Not to be confused with the pulse: 60 entered here describes severe "
                "respiratory distress, not a normal heart rate."
            ),
        },
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
        aide={
            "fr": (
                "Le premier chiffre de la mesure, le plus élevé des deux : une "
                "pression annoncée « 12/8 » se saisit 120."
            ),
            "en": (
                "The first and higher of the two numbers: a blood pressure read as "
                "“120 over 80” is entered as 120."
            ),
        },
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
        aide={
            "fr": "Battements par minute, patient au repos. 60 à 100 chez l'adulte.",
            "en": "Beats per minute, patient at rest. 60 to 100 in an adult.",
        },
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
        aide={
            "fr": (
                "En degrés Celsius, une décimale. Le barème retient une urgence "
                "modérée à partir de 39 °C."
            ),
            "en": (
                "In degrees Celsius, one decimal. The rule set flags moderate "
                "priority from 39 °C upwards."
            ),
        },
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
        aide={
            "fr": (
                "Échelle numérique, telle que le patient l'évalue lui-même : "
                "0 aucune douleur, 10 douleur maximale imaginable. "
                "C'est son chiffre, pas une appréciation de l'accueil."
            ),
            "en": (
                "Numeric rating scale, as the patient rates it themselves: "
                "0 no pain, 10 worst pain imaginable. "
                "It is their number, not the desk's assessment."
            ),
        },
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
    aide={
        "fr": (
            "En années révolues. Le barème et le modèle n'ont été construits et "
            "mesurés que sur des adultes : la pédiatrie est hors du périmètre."
        ),
        "en": (
            "In completed years. The rule set and the model were built and measured "
            "on adults only: paediatrics is out of scope."
        ),
    },
)

QUESTION_SEXE: Final[Question] = Question(
    cle="sexe",
    libelle={"fr": "Quel est le sexe du patient ?", "en": "What is the patient's sex?"},
    type_reponse=TypeReponse.CHOIX,
    choix={"fr": ("masculin", "féminin"), "en": ("male", "female")},
)

# Les bornes physiologiques vivent avec la question qui les affiche, et c'est
# ce meme tableau qui sert a refuser une saisie. Une borne montree a l'accueil
# mais non appliquee par le service laisserait passer une SpO2 a 150 % -- qui
# ne declenche aucun critere, et donc ressort en prise en charge differee.
# La diastolique n'est jamais demandee par le questionnaire, mais un client du
# SIH peut la poster : elle a besoin de ses bornes, elle aussi.
BORNES_CONSTANTES: Final[dict[str, tuple[float, float]]] = {
    "pression_diastolique": (20, 150),
}


QUESTION_ANTECEDENTS: Final[Question] = Question(
    cle="antecedents",
    libelle={
        "fr": "Le patient a-t-il des antécédents médicaux connus ? (sinon, répondre « aucun »)",
        "en": "Does the patient have any known medical history? (otherwise answer “none”)",
    },
    type_reponse=TypeReponse.TEXTE,
)


def bornes(cle: str) -> tuple[float, float] | None:
    """Bornes admissibles pour une cle, ou None quand la valeur est libre."""
    return _BORNES.get(cle)


_BORNES: Final[dict[str, tuple[float, float]]] = {
    **BORNES_CONSTANTES,
    **{
        question.cle: (question.minimum, question.maximum)
        for question in (*QUESTIONS_CONSTANTES, QUESTION_AGE)
        if question.minimum is not None and question.maximum is not None
    },
}


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

    Deux passes, dans cet ordre. Le motif de recours d'abord, parce qu'il decrit
    la presentation. Le vocabulaire de ses symptomes ensuite, parce qu'un patient
    ne se presente pas toujours avec le terme clinique : « toux » est un
    symptome de la dyspnee, jamais un motif du bareme, et sans cette seconde
    passe il tombait dans le repli general -- on lui demandait s'il a des
    « troubles de la vigilance » au lieu d'une cyanose ou d'un tirage.
    """
    normalise = motif.casefold()
    for presentation in PRESENTATIONS:
        libelles = {mot.casefold() for mot in presentation.motif.values()}
        if any(libelle in normalise or normalise in libelle for libelle in libelles):
            return presentation.signes_gravite[langue.value]
    for presentation in PRESENTATIONS:
        # Ici, l'inclusion ne va que dans un sens : le symptome doit apparaitre
        # dans ce qui a ete saisi. L'inverse ferait matcher un motif de deux
        # lettres sur n'importe quel symptome qui les contient.
        symptomes = {
            mot.casefold() for libelles in presentation.symptomes.values() for mot in libelles
        }
        if any(symptome in normalise for symptome in symptomes):
            return presentation.signes_gravite[langue.value]
    return SIGNES_GENERAUX[langue.value]


AIDE_SIGNES: Final[dict[str, str]] = {
    "fr": (
        "Les signes proposés ici dépendent du motif que vous venez de saisir : "
        "on ne dépiste pas les mêmes chez un patient venu pour une douleur "
        "thoracique et chez un patient venu pour une entorse.\n\n"
        "Répondre « oui » signifie qu'au moins un de ces signes est présent, et "
        "suffit à classer le cas en urgence maximale : le recueil s'arrête là, "
        "sans demander les constantes. Ne répondez « oui » que si vous constatez "
        "réellement l'un d'eux."
    ),
    "en": (
        "The signs listed here depend on the reason for attendance you just "
        "entered: a patient presenting with chest pain and one presenting with a "
        "sprain are not screened for the same things.\n\n"
        "Answering “yes” means at least one of these signs is present, and is "
        "enough to rate the case as maximum priority: the interview stops there, "
        "without asking for vital signs. Only answer “yes” if you actually "
        "observe one of them."
    ),
}


def question_signes(motif: str, langue: Langue) -> Question:
    """Construit la question de depistage des signes de gravite."""
    signes = signes_a_rechercher(motif, langue)
    liste = ", ".join(signes)
    libelle = {
        "fr": f"Un de ces signes est-il présent : {liste} ?",
        "en": f"Is any of these signs present: {liste}?",
    }
    return Question(
        cle="signe_gravite",
        libelle=libelle,
        type_reponse=TypeReponse.OUI_NON,
        aide=AIDE_SIGNES,
    )


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
