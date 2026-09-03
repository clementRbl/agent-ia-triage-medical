"""Logique de triage : combinaison du modele et du garde-fou par regles.

Le modele fine-tune produit le niveau et son explication -- c'est lui qu'on a
mesure. Le bareme explicite recalcule le niveau de son cote. Les deux sont
confrontes :

- accord : le niveau est rendu tel quel ;
- le modele annonce **moins** grave que le bareme : le niveau est releve et
  l'ecart est consigne. C'est le seul sens ou le garde-fou intervient. Un
  sous-triage laisse un patient grave en salle d'attente ; un sur-triage
  encombre le service. Les deux ne se valent pas.
- le modele annonce **plus** grave : sa prudence est conservee.

Le desaccord n'est jamais efface : il est journalise, parce que sa frequence
est en soi une mesure de la fiabilite du modele en service.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from threading import Lock

from triage.api.journal import Evenement, Journal
from triage.api.moteur import Moteur
from triage.api.questionnaire import Entretien, Question
from triage.schema import Constantes, Langue, NiveauPriorite
from triage.training.evaluation import RANG, extraire_niveau


@dataclass(frozen=True)
class Evaluation:
    """Resultat d'un triage, model et regles compris."""

    niveau: NiveauPriorite
    explication: str
    criteres: list[str]
    niveau_modele: NiveauPriorite | None
    niveau_regles: NiveauPriorite
    escalade: bool
    moteur: str
    modele: str
    latence_ms: float


def arbitrer(
    niveau_modele: NiveauPriorite | None, niveau_regles: NiveauPriorite
) -> tuple[NiveauPriorite, bool]:
    """Retient le plus grave des deux niveaux ; signale l'ecart.

    Quand le modele n'annonce aucun niveau lisible -- reponse tronquee, format
    inattendu -- le bareme tranche seul. Rendre « indeterminé » a un agent
    d'accueil serait la pire des sorties : il faudrait decider sans rien.
    """
    if niveau_modele is None:
        return niveau_regles, True
    if RANG[niveau_modele] < RANG[niveau_regles]:
        return niveau_regles, True
    return niveau_modele, False


@dataclass
class ServiceTriage:
    """Orchestration d'un entretien : questions, modele, garde-fou, journal."""

    moteur: Moteur
    journal: Journal
    _entretiens: dict[str, Entretien] = field(default_factory=dict)
    _verrou: Lock = field(default_factory=Lock, repr=False)

    def ouvrir(self, langue: Langue) -> tuple[str, Entretien]:
        session = uuid.uuid4().hex
        entretien = Entretien(langue=langue)
        with self._verrou:
            self._entretiens[session] = entretien
        self.journal.consigner(
            session, Evenement.OUVERTURE, {"langue": langue.value, "moteur": self.moteur.nom}
        )
        return session, entretien

    def entretien(self, session: str) -> Entretien | None:
        with self._verrou:
            return self._entretiens.get(session)

    def consigner_question(self, session: str, question: Question, langue: Langue) -> None:
        self.journal.consigner(
            session,
            Evenement.QUESTION,
            {"cle": question.cle, "question": question.texte(langue)},
        )

    def enregistrer_reponse(
        self, session: str, entretien: Entretien, cle: str, valeur: str
    ) -> None:
        """Applique une reponse a l'entretien et la journalise."""
        appliquer_reponse(entretien, cle, valeur)
        entretien.questions_posees.append(cle)
        self.journal.consigner(session, Evenement.REPONSE, {"cle": cle, "reponse": valeur})

    def trier(self, session: str, entretien: Entretien) -> Evaluation:
        """Interroge le modele, confronte au bareme, journalise le resultat."""
        niveau_regles, criteres = entretien.niveau_regles()
        instruction = entretien.instruction()
        generation = self.moteur.generer(instruction, entretien.langue)
        niveau_modele = extraire_niveau(generation.texte)
        niveau, escalade = arbitrer(niveau_modele, niveau_regles)

        evaluation = Evaluation(
            niveau=niveau,
            explication=generation.texte,
            criteres=criteres,
            niveau_modele=niveau_modele,
            niveau_regles=niveau_regles,
            escalade=escalade,
            moteur=generation.moteur,
            modele=generation.modele,
            latence_ms=generation.latence_ms,
        )
        if escalade:
            self.journal.consigner(
                session,
                Evenement.ESCALADE,
                {
                    "niveau_modele": niveau_modele.value if niveau_modele else None,
                    "niveau_regles": niveau_regles.value,
                    "niveau_retenu": niveau.value,
                },
            )
        self.journal.consigner(
            session,
            Evenement.TRIAGE,
            {
                "niveau": niveau.value,
                "criteres": criteres,
                "explication": generation.texte,
                "moteur": generation.moteur,
                "modele": generation.modele,
                "latence_ms": generation.latence_ms,
                "escalade": escalade,
            },
        )
        return evaluation

    def cloturer(self, session: str) -> None:
        with self._verrou:
            self._entretiens.pop(session, None)


_AFFIRMATIONS = {"oui", "o", "yes", "y", "true", "vrai", "1"}
_NEGATIONS = {"non", "n", "no", "false", "faux", "0"}
_AUCUN = {"aucun", "aucune", "none", "no", "non", "rien", "nothing"}

_CONSTANTES_ENTIERES = frozenset(
    {
        "frequence_cardiaque",
        "pression_systolique",
        "pression_diastolique",
        "frequence_respiratoire",
        "saturation",
        "glasgow",
        "douleur",
    }
)


def appliquer_reponse(entretien: Entretien, cle: str, valeur: str) -> None:
    """Range une reponse dans l'entretien, en refusant ce qui n'est pas valide."""
    texte = valeur.strip()
    match cle:
        case "motif":
            entretien.motif = texte
        case "age":
            entretien.age = _entier(texte, cle, 0, 120)
        case "sexe":
            entretien.sexe = texte
        case "signe_gravite":
            entretien.signe_gravite = _booleen(texte)
        case "antecedents":
            entretien.antecedents = (
                ["aucun" if entretien.langue is Langue.FR else "none"]
                if texte.casefold() in _AUCUN
                else [part.strip() for part in texte.split(",") if part.strip()]
            )
        case "temperature":
            _poser(entretien.constantes, cle, _decimal(texte, cle, 30.0, 43.0))
        case _ if cle in _CONSTANTES_ENTIERES:
            _poser(entretien.constantes, cle, _entier(texte, cle, -1000, 1000))
        case _:
            raise ValueError(f"Question inconnue : {cle!r}")


def _poser(constantes: Constantes, cle: str, valeur: float) -> None:
    setattr(constantes, cle, valeur)


def _entier(texte: str, cle: str, minimum: int, maximum: int) -> int:
    try:
        valeur = int(texte)
    except ValueError as erreur:
        raise ValueError(f"{cle} : « {texte} » n'est pas un nombre entier") from erreur
    if not minimum <= valeur <= maximum:
        raise ValueError(f"{cle} : {valeur} hors des bornes [{minimum}, {maximum}]")
    return valeur


def _decimal(texte: str, cle: str, minimum: float, maximum: float) -> float:
    try:
        valeur = float(texte.replace(",", "."))
    except ValueError as erreur:
        raise ValueError(f"{cle} : « {texte} » n'est pas un nombre") from erreur
    if not minimum <= valeur <= maximum:
        raise ValueError(f"{cle} : {valeur} hors des bornes [{minimum}, {maximum}]")
    return valeur


def _booleen(texte: str) -> bool:
    normalise = texte.casefold()
    if normalise in _AFFIRMATIONS:
        return True
    if normalise in _NEGATIONS:
        return False
    raise ValueError(f"Réponse attendue par oui ou non, reçue « {texte} »")
