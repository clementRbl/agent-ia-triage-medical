"""Anonymisation des textes cliniques (Presidio + spaCy).

Le corpus utilise des cas cliniques publies, mais la chaine est concue pour
traiter des donnees hospitalieres reelles : elle constitue la brique RGPD du
projet.

Choix documente : le masquage est *cible*. On retire ce qui identifie une
personne (nom, contact, identifiant national) et on **conserve** ce qui porte
du sens clinique (localisation geographique, duree, constante vitale). Masquer
"Gabon" dans un cas de chimioprophylaxie du paludisme detruirait le cas.
Voir docs/03d-anonymisation-rgpd.md.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Final

from presidio_analyzer import (
    AnalyzerEngine,
    Pattern,
    PatternRecognizer,
    RecognizerRegistry,
    RecognizerResult,
)
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

from triage.data.lexique_medical import est_faux_positif

SUPPORTED_LANGUAGES: Final[tuple[str, ...]] = ("fr", "en")

_SPACY_MODELS: Final[dict[str, str]] = {
    "fr": "fr_core_news_md",
    "en": "en_core_web_md",
}

# Entites retirees. Volontairement sans LOCATION ni DATE_TIME generique :
# cf. docstring du module.
DEFAULT_ENTITIES: Final[tuple[str, ...]] = (
    "PERSON",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "IBAN_CODE",
    "FR_NIR",
    "FR_CIVILITE",
    "FR_DATE_ABSOLUE",
    "ETABLISSEMENT_SANTE",
)

# Remplacement par un marqueur type plutot que par une suppression : la phrase
# reste grammaticale, donc exploitable pour le fine-tuning.
DEFAULT_OPERATORS: Final[dict[str, str]] = {
    "PERSON": "<PATIENT>",
    "FR_CIVILITE": "<PATIENT>",
    "EMAIL_ADDRESS": "<EMAIL>",
    "PHONE_NUMBER": "<TELEPHONE>",
    "IBAN_CODE": "<IBAN>",
    "FR_NIR": "<NIR>",
    "FR_DATE_ABSOLUE": "<DATE>",
    "ETABLISSEMENT_SANTE": "<ETABLISSEMENT>",
}

# Numero de securite sociale francais : 13 chiffres + cle de 2 chiffres.
# Donnee de sante directement identifiante, priorite absolue.
_NIR_PATTERN = Pattern(
    name="nir_fr",
    regex=r"\b[12][ ]?\d{2}[ ]?(?:0[1-9]|1[0-2]|20|3[0-9]|4[0-2]|[5-9][0-9])[ ]?"
    r"(?:0[1-9]|[1-9]\d|2A|2B)[ ]?\d{3}[ ]?\d{3}(?:[ ]?\d{2})?\b",
    score=0.85,
)

# "Monsieur R.", "Mme D...", "M. Dupont" : spaCy ne reconnait pas un patronyme
# reduit a une initiale, or c'est la forme dominante dans MediQAl.
_CIVILITE_PATTERN = Pattern(
    name="civilite_initiale_fr",
    # Capture le patronyme complet apres la civilite, y compris les formes
    # "Monsieur V. Joseph" ou "Mme Marie Dupont" : s'arreter au premier token
    # laissait fuiter le reste du nom.
    regex=r"\b(?:Monsieur|Madame|Mademoiselle|M\.|Mme|Mlle|Mr)"
    r"(?:\s+(?:[A-ZÉÈÀÂÎÔÛ][\w'’\-]*\.?|[A-Z]\.{1,3})){1,3}",
    score=0.8,
)

# Dates absolues uniquement. Les durees ("depuis 3 jours") sont cliniquement
# indispensables et ne doivent surtout pas etre masquees.
_DATE_ABSOLUE_PATTERN = Pattern(
    name="date_absolue_fr",
    regex=r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"
    r"|\d{1,2}\s+(?:janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout"
    r"|septembre|octobre|novembre|décembre|decembre)\s+\d{4})\b",
    score=0.8,
)

_ETABLISSEMENT_PATTERN = Pattern(
    name="etablissement_sante_fr",
    regex=r"\b(?:CHU|CHR|CHRU|CH|Hôpital|Hopital|Clinique|Centre Hospitalier)"
    r"(?:\s+(?:de|du|des|d'))?\s+[A-ZÉÈÀ][\w'’\-]+",
    score=0.7,
)

_EMAIL_PATTERN = Pattern(
    name="email_fr",
    regex=r"\b[\w.%+\-]+@[\w.\-]+\.[A-Za-z]{2,}\b",
    score=0.9,
)

_TELEPHONE_PATTERN = Pattern(
    name="telephone_fr",
    regex=r"\b(?:(?:\+33|0033)\s?[1-9]|0[1-9])(?:[\s.\-]?\d{2}){4}\b",
    score=0.8,
)


def _french_recognizers() -> list[PatternRecognizer]:
    """Reconnaisseurs specifiques au francais, absents du socle Presidio."""
    return [
        PatternRecognizer(
            supported_entity="FR_NIR",
            supported_language="fr",
            patterns=[_NIR_PATTERN],
            context=["sécurité sociale", "nir", "insee", "assuré"],
        ),
        PatternRecognizer(
            supported_entity="FR_CIVILITE",
            supported_language="fr",
            patterns=[_CIVILITE_PATTERN],
        ),
        PatternRecognizer(
            supported_entity="FR_DATE_ABSOLUE",
            supported_language="fr",
            patterns=[_DATE_ABSOLUE_PATTERN],
        ),
        PatternRecognizer(
            supported_entity="ETABLISSEMENT_SANTE",
            supported_language="fr",
            patterns=[_ETABLISSEMENT_PATTERN],
        ),
        PatternRecognizer(
            supported_entity="EMAIL_ADDRESS",
            supported_language="fr",
            patterns=[_EMAIL_PATTERN],
        ),
        PatternRecognizer(
            supported_entity="PHONE_NUMBER",
            supported_language="fr",
            patterns=[_TELEPHONE_PATTERN],
        ),
    ]


# Age : conserve car cliniquement determinant pour le triage. Seuls les grands
# ages sont generalises, ceux-ci etant re-identifiants (principe repris du
# Safe Harbor HIPAA, seuil 90 ans).
_AGE_RE = re.compile(r"\b(\d{2,3})\s*(ans|ann[ée]es|years?[- ]old)\b", re.IGNORECASE)
_AGE_SEUIL: Final[int] = 90


def generaliser_grands_ages(texte: str, seuil: int = _AGE_SEUIL) -> str:
    """Remplace les ages >= seuil par une tranche, en gardant le reste intact."""

    def _remplacer(m: re.Match[str]) -> str:
        return f"{seuil}+ {m.group(2)}" if int(m.group(1)) >= seuil else m.group(0)

    return _AGE_RE.sub(_remplacer, texte)


@dataclass
class ResultatAnonymisation:
    """Texte anonymise et trace des entites retirees (auditabilite)."""

    texte: str
    entites: dict[str, int] = field(default_factory=dict)

    @property
    def nb_entites(self) -> int:
        return sum(self.entites.values())


class Anonymiseur:
    """Encapsule les moteurs Presidio pour un usage bilingue fr/en."""

    def __init__(
        self,
        entites: tuple[str, ...] = DEFAULT_ENTITIES,
        operateurs: dict[str, str] | None = None,
        seuil_score: float = 0.4,
        filtrer_faux_positifs: bool = True,
    ) -> None:
        self.entites = entites
        self.operateurs = operateurs or DEFAULT_OPERATORS
        self.seuil_score = seuil_score
        self.filtrer_faux_positifs = filtrer_faux_positifs
        self._analyzer = self._construire_analyzer()
        self._anonymizer = AnonymizerEngine()

    @staticmethod
    def _construire_analyzer() -> AnalyzerEngine:
        provider = NlpEngineProvider(
            nlp_configuration={
                "nlp_engine_name": "spacy",
                "models": [
                    {"lang_code": lang, "model_name": modele}
                    for lang, modele in _SPACY_MODELS.items()
                ],
            }
        )
        registry = RecognizerRegistry(supported_languages=list(SUPPORTED_LANGUAGES))
        registry.load_predefined_recognizers(languages=list(SUPPORTED_LANGUAGES))
        for reconnaisseur in _french_recognizers():
            registry.add_recognizer(reconnaisseur)
        return AnalyzerEngine(
            nlp_engine=provider.create_engine(),
            registry=registry,
            supported_languages=list(SUPPORTED_LANGUAGES),
        )

    def analyser(
        self,
        texte: str,
        langue: str = "fr",
        entites: tuple[str, ...] | None = None,
    ) -> list[RecognizerResult]:
        """Detecte les entites sans anonymiser (utilise par le controle qualite)."""
        if langue not in SUPPORTED_LANGUAGES:
            raise ValueError(f"Langue non supportée : {langue!r}")
        resultats = self._analyzer.analyze(
            text=texte,
            language=langue,
            entities=list(entites or self.entites),
            score_threshold=self.seuil_score,
        )
        if not self.filtrer_faux_positifs:
            return resultats
        # Le detecteur de noms propres confond le vocabulaire medical avec des
        # patronymes : on ecarte ces detections plutot que de mutiler le texte.
        return [
            r
            for r in resultats
            if r.entity_type != "PERSON" or not est_faux_positif(texte, r.start, r.end)
        ]

    def anonymiser(self, texte: str, langue: str = "fr") -> ResultatAnonymisation:
        if not texte or not texte.strip():
            return ResultatAnonymisation(texte=texte)

        resultats = self.analyser(texte, langue=langue)
        compte: dict[str, int] = {}
        for r in resultats:
            compte[r.entity_type] = compte.get(r.entity_type, 0) + 1

        # Presidio declare deux classes `RecognizerResult` distinctes mais
        # structurellement identiques, une par moteur. Le passage de l'une a
        # l'autre est l'usage prevu par la bibliotheque.
        sortie = self._anonymizer.anonymize(
            text=texte,
            analyzer_results=resultats,  # ty: ignore[invalid-argument-type]
            operators={
                entite: OperatorConfig("replace", {"new_value": marqueur})
                for entite, marqueur in self.operateurs.items()
            },
        ).text
        return ResultatAnonymisation(texte=generaliser_grands_ages(sortie), entites=compte)
