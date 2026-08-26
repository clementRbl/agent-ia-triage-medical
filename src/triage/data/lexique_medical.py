"""Lexique servant a ecarter les faux positifs du detecteur de noms propres.

Constat mesure sur MediQAl : spaCy classe en PERSON de nombreux termes
medicaux capitalises (eponymes, analyses biologiques, signes cliniques).
Les masquer detruirait l'information clinique -- "signe de Babinski" deviendrait
"signe de <PATIENT>". Ce module regroupe les regles d'exclusion.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Final

# Un eponyme est introduit par un terme declencheur : "maladie de Parkinson",
# "signe de Babinski", "intervention de Senning". La regle de contexte couvre
# les eponymes absents du lexique.
CONTEXTE_EPONYME: Final[re.Pattern[str]] = re.compile(
    r"\b(?:maladies?|syndromes?|signes?|réflexes?|reflexes?|manœuvres?|manoeuvres?"
    r"|interventions?|opérations?|operations?|techniques?|tests?|épreuves?|epreuves?"
    r"|scores?|échelles?|echelles?|indices?|classifications?|critères?|criteres?"
    r"|stades?|grades?|lois?|methodes?|méthodes?|triades?|fractures?|tumeurs?"
    r"|lignes?|points?|canal|canaux|artères?|arteres?|veines?|nerfs?|gaines?"
    r"|sondes?|prothèses?|protheses?|cellules?|corps|anses?)\s+(?:de|d'|d’|du|des)\s*$",
    re.IGNORECASE,
)

_TERMES_MEDICAUX: Final[frozenset[str]] = frozenset(
    {
        # Eponymes frequents (pathologies, signes, interventions)
        "parkinson",
        "alzheimer",
        "babinski",
        "kawasaki",
        "senning",
        "crohn",
        "hodgkin",
        "basedow",
        "cushing",
        "addison",
        "graves",
        "raynaud",
        "guillain",
        "barre",
        "horton",
        "wegener",
        "behcet",
        "marfan",
        "down",
        "turner",
        "klinefelter",
        "duchenne",
        "charcot",
        "willebrand",
        "gilbert",
        "damoiseau",
        "murphy",
        "blumberg",
        "homans",
        "kernig",
        "brudzinski",
        "glasgow",
        "apgar",
        "ranson",
        "child",
        "pugh",
        "framingham",
        "bishop",
        "fontan",
        "blalock",
        "rastelli",
        "mustard",
        "ross",
        "bentall",
        "hartmann",
        "billroth",
        "whipple",
        "roux",
        "mallory",
        "weiss",
        "boerhaave",
        "ogilvie",
        "paget",
        "bowen",
        "quincke",
        "lyell",
        "stevens",
        "johnson",
        "wolff",
        "brugada",
        "romano",
        "ward",
        "purkinje",
        "his",
        "bachmann",
        "koch",
        "wilson",
        "menetrier",
        "ménétrier",
        "vaquez",
        "biermer",
        "waldenstrom",
        "burkitt",
        "ewing",
        "wilms",
        "hirschsprung",
        "meckel",
        "barrett",
        "zollinger",
        "ellison",
        "conn",
        "sheehan",
        "simmonds",
        "reiter",
        "sjogren",
        "sjögren",
        "takayasu",
        "buerger",
        "leriche",
        "cockett",
        "dupuytren",
        "pott",
        "scheuermann",
        "osgood",
        "schlatter",
        "perthes",
        "colles",
        "pouteau",
        "monteggia",
        "galeazzi",
        "bennett",
        "jones",
        # Analyses biologiques et parametres
        "hémoglobine",
        "hemoglobine",
        "hématocrite",
        "hematocrite",
        "leucocytes",
        "thrombocytes",
        "plaquettes",
        "créatinine",
        "creatinine",
        "fibrinogène",
        "fibrinogene",
        "ionogramme",
        "hémogramme",
        "hemogramme",
        "céphaline",
        "cephaline",
        "protéines",
        "proteines",
        "albumine",
        "bilirubine",
        "urée",
        "uree",
        "glycémie",
        "glycemie",
        "kaliémie",
        "kaliemie",
        "natrémie",
        "natremie",
        "calcémie",
        "calcemie",
        "réticulocytes",
        "reticulocytes",
        "transaminases",
        "phosphatases",
        "lipase",
        "amylase",
        "troponine",
        "ferritine",
        "transferrine",
        "haptoglobine",
        "prothrombine",
        "sang",
        # Signes et termes cliniques capitalises en debut de ligne
        "cyanose",
        "hépatosplénomégalie",
        "hepatosplenomegalie",
        "splénomégalie",
        "splenomegalie",
        "hépatomégalie",
        "hepatomegalie",
        "adénopathie",
        "adenopathie",
        "nulligeste",
        "primigeste",
        "multipare",
        "nullipare",
        "dyspnée",
        "dyspnee",
        "asthénie",
        "asthenie",
        "anorexie",
        "amaigrissement",
        "sensible",
        "irrégulier",
        "irregulier",
        "déclive",
        "declive",
        "régulier",
        "regulier",
        "hypertrophie",
        "auscultation",
        "palpation",
        "percussion",
        "inspection",
        "examen",
        "traitement",
        "évolution",
        "evolution",
        "antécédents",
        "antecedents",
        "constantes",
        "biologie",
        "imagerie",
        "chlamydiae",
        "chlamydia",
        "candida",
        "aspergillus",
        "listeria",
        "salmonella",
        "shigella",
        "klebsiella",
        "proteus",
        "serratia",
        "escherichia",
        "helicobacter",
        "mycoplasma",
        "legionella",
        "yersinia",
        "hashimoto",
        "sokolov",
        "lyon",
        "gazométrie",
        "gazometrie",
        "spirométrie",
        "spirometrie",
        "scintigraphie",
        "coronarographie",
        "fibroscopie",
        "échographie",
        "echographie",
        "radiographie",
        "tomodensitométrie",
        "tomodensitometrie",
    }
)

# Abreviations de compte rendu prises pour des noms ("Sg" = sang).
_ABREVIATIONS: Final[frozenset[str]] = frozenset({"sg", "sp", "ecbu", "tp", "tca", "vs", "crp"})

# Symboles chimiques des comptes rendus de biologie, pris pour des initiales.
_SYMBOLES_CHIMIQUES: Final[frozenset[str]] = frozenset(
    {"na", "k", "cl", "ca", "mg", "fe", "p", "se", "zn", "cu", "li", "hco3", "po4"}
)


def _normaliser(terme: str) -> str:
    sans_accent = unicodedata.normalize("NFKD", terme.casefold())
    return "".join(c for c in sans_accent if not unicodedata.combining(c)).strip(" .®©-'’")


def est_terme_medical(span: str) -> bool:
    """Vrai si le span correspond a du vocabulaire medical, pas a une personne."""
    tokens = [t for t in re.split(r"[\s'’\-]+", span) if t]
    if not tokens:
        return True
    normalises = {_normaliser(t) for t in tokens}
    lexique = {_normaliser(t) for t in _TERMES_MEDICAUX}
    if span.rstrip(" .").endswith(("®", "™")):  # nom commercial de medicament
        return True
    return bool(normalises & (lexique | _ABREVIATIONS | _SYMBOLES_CHIMIQUES))


def est_faux_positif(texte: str, debut: int, fin: int) -> bool:
    """Decide si une detection PERSON doit etre ecartee.

    Trois regles, dans l'ordre de cout croissant :
      1. un nom propre francais commence par une majuscule ;
      2. un token isole d'une seule lettre n'identifie personne ;
      3. le span est un terme medical, ou suit un declencheur d'eponyme.
    """
    span = texte[debut:fin].strip()
    if not span:
        return True
    if not span[0].isupper():
        return True
    if len(span.rstrip(".")) <= 1:
        return True
    if est_terme_medical(span):
        return True
    return bool(CONTEXTE_EPONYME.search(texte[max(0, debut - 40) : debut]))
