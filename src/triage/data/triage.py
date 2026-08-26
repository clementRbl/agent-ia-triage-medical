"""Construction des cas de triage structures (bloc D).

Pourquoi ce bloc existe : ni MediQAl ni UltraMedical ne portent de niveau de
priorite ni de constantes vitales exploitables (3 % des cas cliniques, mesure
dans notebooks/01_exploration_corpus.ipynb). Sans lui, le champ
`niveau_priorite` du schema reste vide et le **taux de sous-triage** -- la
metrique de securite du projet -- est impossible a mesurer.

Principe : les constantes sont tirees au sort dans des bornes physiologiques,
puis le niveau de priorite en est **deduit** par des criteres explicites. Le
label n'est jamais invente : il est la consequence verifiable du tableau
clinique. Une regle fausse est donc un bug detectable par un test, pas une
approximation noyee dans les donnees.

Bareme : transposition simplifiee de l'echelle de tri francaise FRENCH, ramenee
aux trois niveaux demandes par le CHSA. Il n'a **pas ete valide par un
clinicien** : c'est une limite assumee du POC, documentee dans le rapport.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Final

from triage.schema import Bloc, Constantes, Enregistrement, Langue, NiveauPriorite

LICENCE = "construit (règles explicites)"
SOURCE = "triage_regles"


@dataclass(frozen=True)
class Presentation:
    """Un motif de recours aux urgences et son vocabulaire clinique."""

    cle: str
    motif: dict[str, str]
    symptomes: dict[str, tuple[str, ...]]
    signes_gravite: dict[str, tuple[str, ...]]
    antecedents: dict[str, tuple[str, ...]]
    age_min: int = 18
    age_max: int = 92


PRESENTATIONS: Final[tuple[Presentation, ...]] = (
    Presentation(
        cle="douleur_thoracique",
        motif={"fr": "douleur thoracique", "en": "chest pain"},
        symptomes={
            "fr": ("douleur rétrosternale", "oppression thoracique", "sueurs", "nausées"),
            "en": ("retrosternal pain", "chest tightness", "sweating", "nausea"),
        },
        signes_gravite={
            "fr": ("irradiation au bras gauche", "douleur au repos", "pâleur", "malaise"),
            "en": ("radiation to the left arm", "pain at rest", "pallor", "faintness"),
        },
        antecedents={
            "fr": ("hypertension artérielle", "tabagisme", "dyslipidémie", "diabète de type 2"),
            "en": ("hypertension", "smoking", "dyslipidaemia", "type 2 diabetes"),
        },
        age_min=35,
    ),
    Presentation(
        cle="dyspnee",
        motif={"fr": "dyspnée", "en": "shortness of breath"},
        symptomes={
            "fr": ("essoufflement", "toux", "expectorations", "sifflements"),
            "en": ("breathlessness", "cough", "sputum", "wheezing"),
        },
        signes_gravite={
            "fr": ("cyanose", "tirage intercostal", "impossibilité de parler en phrases"),
            "en": ("cyanosis", "intercostal retractions", "inability to speak in sentences"),
        },
        antecedents={
            "fr": ("BPCO", "asthme", "insuffisance cardiaque", "tabagisme"),
            "en": ("COPD", "asthma", "heart failure", "smoking"),
        },
    ),
    Presentation(
        cle="deficit_neurologique",
        motif={"fr": "déficit neurologique brutal", "en": "sudden neurological deficit"},
        symptomes={
            "fr": ("faiblesse d'un hémicorps", "troubles de la parole", "céphalée"),
            "en": ("unilateral weakness", "speech difficulty", "headache"),
        },
        signes_gravite={
            "fr": ("asymétrie faciale", "aphasie", "troubles de la vigilance"),
            "en": ("facial asymmetry", "aphasia", "reduced alertness"),
        },
        antecedents={
            "fr": ("fibrillation auriculaire", "hypertension artérielle", "AVC antérieur"),
            "en": ("atrial fibrillation", "hypertension", "previous stroke"),
        },
        age_min=45,
    ),
    Presentation(
        cle="douleur_abdominale",
        motif={"fr": "douleur abdominale", "en": "abdominal pain"},
        symptomes={
            "fr": ("douleur en fosse iliaque droite", "nausées", "vomissements", "anorexie"),
            "en": ("right iliac fossa pain", "nausea", "vomiting", "loss of appetite"),
        },
        signes_gravite={
            "fr": (
                "défense abdominale",
                "arrêt des matières et des gaz",
                "vomissements fécaloïdes",
            ),
            "en": ("abdominal guarding", "absence of stool and flatus", "faeculent vomiting"),
        },
        antecedents={
            "fr": ("chirurgie abdominale", "maladie de Crohn", "lithiase biliaire"),
            "en": ("abdominal surgery", "Crohn disease", "gallstones"),
        },
    ),
    Presentation(
        cle="traumatisme_membre",
        motif={"fr": "traumatisme d'un membre", "en": "limb injury"},
        symptomes={
            "fr": ("douleur du poignet", "œdème local", "impotence fonctionnelle"),
            "en": ("wrist pain", "local swelling", "loss of function"),
        },
        signes_gravite={
            "fr": ("déformation évidente", "abolition du pouls distal", "ouverture cutanée"),
            "en": ("obvious deformity", "absent distal pulse", "open wound"),
        },
        antecedents={
            "fr": ("ostéoporose", "chute à répétition", "aucun"),
            "en": ("osteoporosis", "recurrent falls", "none"),
        },
    ),
    Presentation(
        cle="fievre",
        motif={"fr": "fièvre", "en": "fever"},
        symptomes={
            "fr": ("frissons", "asthénie", "céphalée", "myalgies"),
            "en": ("chills", "fatigue", "headache", "muscle aches"),
        },
        signes_gravite={
            "fr": ("marbrures", "purpura", "confusion"),
            "en": ("mottled skin", "purpura", "confusion"),
        },
        antecedents={
            "fr": ("immunodépression", "chimiothérapie en cours", "splénectomie"),
            "en": ("immunosuppression", "ongoing chemotherapy", "splenectomy"),
        },
    ),
    Presentation(
        cle="malaise",
        motif={"fr": "malaise avec perte de connaissance", "en": "syncope"},
        symptomes={
            "fr": ("sensation vertigineuse", "sueurs", "vision trouble"),
            "en": ("dizziness", "sweating", "blurred vision"),
        },
        signes_gravite={
            "fr": (
                "perte de connaissance prolongée",
                "traumatisme crânien associé",
                "palpitations",
            ),
            "en": ("prolonged loss of consciousness", "associated head injury", "palpitations"),
        },
        antecedents={
            "fr": ("trouble du rythme", "traitement antihypertenseur", "diabète"),
            "en": ("arrhythmia", "antihypertensive treatment", "diabetes"),
        },
    ),
    Presentation(
        cle="cephalee",
        motif={"fr": "céphalée", "en": "headache"},
        symptomes={
            "fr": ("céphalée frontale", "photophobie", "nausées"),
            "en": ("frontal headache", "photophobia", "nausea"),
        },
        signes_gravite={
            "fr": ("céphalée en coup de tonnerre", "raideur de nuque", "vomissements en jet"),
            "en": ("thunderclap headache", "neck stiffness", "projectile vomiting"),
        },
        antecedents={
            "fr": ("migraine connue", "hypertension artérielle", "aucun"),
            "en": ("known migraine", "hypertension", "none"),
        },
    ),
    Presentation(
        cle="lombalgie",
        motif={"fr": "lombalgie", "en": "low back pain"},
        symptomes={
            "fr": ("douleur lombaire mécanique", "raideur matinale", "contracture"),
            "en": ("mechanical low back pain", "morning stiffness", "muscle spasm"),
        },
        signes_gravite={
            "fr": ("troubles sphinctériens", "anesthésie en selle", "déficit moteur"),
            "en": ("bladder dysfunction", "saddle anaesthesia", "motor deficit"),
        },
        antecedents={
            "fr": ("hernie discale", "port de charges", "aucun"),
            "en": ("disc herniation", "heavy lifting", "none"),
        },
    ),
    Presentation(
        cle="reaction_allergique",
        motif={"fr": "réaction allergique", "en": "allergic reaction"},
        symptomes={
            "fr": ("urticaire", "prurit", "œdème des lèvres"),
            "en": ("hives", "itching", "lip swelling"),
        },
        signes_gravite={
            "fr": ("œdème laryngé", "dysphonie", "bronchospasme"),
            "en": ("laryngeal oedema", "hoarseness", "bronchospasm"),
        },
        antecedents={
            "fr": ("allergie aux hyménoptères", "asthme", "allergie médicamenteuse"),
            "en": ("insect sting allergy", "asthma", "drug allergy"),
        },
    ),
    Presentation(
        cle="plaie_superficielle",
        motif={"fr": "plaie superficielle", "en": "superficial wound"},
        symptomes={
            "fr": ("plaie propre de l'avant-bras", "saignement contrôlé", "douleur modérée"),
            "en": ("clean forearm wound", "controlled bleeding", "moderate pain"),
        },
        signes_gravite={
            "fr": ("saignement actif", "corps étranger profond", "atteinte tendineuse"),
            "en": ("active bleeding", "deep foreign body", "tendon involvement"),
        },
        antecedents={
            "fr": ("vaccination antitétanique à jour", "traitement anticoagulant", "aucun"),
            "en": ("tetanus vaccination up to date", "anticoagulant therapy", "none"),
        },
    ),
    Presentation(
        cle="vomissements",
        motif={"fr": "vomissements et diarrhée", "en": "vomiting and diarrhoea"},
        symptomes={
            "fr": ("vomissements répétés", "diarrhée liquide", "crampes abdominales"),
            "en": ("repeated vomiting", "watery diarrhoea", "abdominal cramps"),
        },
        signes_gravite={
            "fr": ("pli cutané persistant", "oligurie", "somnolence"),
            "en": ("persistent skin fold", "reduced urine output", "drowsiness"),
        },
        antecedents={
            "fr": ("insuffisance rénale chronique", "diabète", "aucun"),
            "en": ("chronic kidney disease", "diabetes", "none"),
        },
    ),
)


# --- Criteres de priorite -------------------------------------------------
#
# Chaque critere est explicite et testable. L'ordre compte : le premier
# declenche emporte la decision, du plus grave au moins grave.


@dataclass(frozen=True)
class Critere:
    """Un seuil objectivable, avec son libelle bilingue pour la justification."""

    cle: str
    libelle: dict[str, str]


CRITERES_MAXIMALE: Final[tuple[Critere, ...]] = (
    Critere("glasgow", {"fr": "score de Glasgow < 14", "en": "Glasgow score < 14"}),
    Critere("saturation", {"fr": "SpO2 < 90 %", "en": "SpO2 < 90%"}),
    Critere(
        "frequence_respiratoire",
        {"fr": "fréquence respiratoire > 30/min ou < 8/min", "en": "respiratory rate > 30 or < 8"},
    ),
    Critere(
        "pression_systolique",
        {"fr": "pression artérielle systolique < 90 mmHg", "en": "systolic blood pressure < 90"},
    ),
    Critere(
        "frequence_cardiaque",
        {"fr": "fréquence cardiaque > 130/min ou < 40/min", "en": "heart rate > 130 or < 40"},
    ),
    Critere(
        "signe_gravite",
        {"fr": "présence d'un signe de gravité", "en": "presence of a red-flag sign"},
    ),
)

CRITERES_MODEREE: Final[tuple[Critere, ...]] = (
    Critere("saturation", {"fr": "SpO2 entre 90 et 94 %", "en": "SpO2 between 90 and 94%"}),
    Critere(
        "frequence_respiratoire",
        {"fr": "fréquence respiratoire entre 25 et 30/min", "en": "respiratory rate 25-30"},
    ),
    Critere(
        "pression_systolique",
        {"fr": "pression artérielle systolique entre 90 et 100 mmHg", "en": "systolic BP 90-100"},
    ),
    Critere(
        "frequence_cardiaque",
        {"fr": "fréquence cardiaque entre 110 et 130/min", "en": "heart rate 110-130"},
    ),
    Critere("temperature", {"fr": "température ≥ 39 °C", "en": "temperature >= 39 °C"}),
    Critere("douleur", {"fr": "douleur évaluée à 5/10 ou plus", "en": "pain score 5/10 or above"}),
)


def _declencheurs_maximale(c: Constantes, signe_gravite: bool) -> list[Critere]:
    """Criteres d'urgence maximale effectivement remplis par ce tableau."""
    remplis = []
    for critere in CRITERES_MAXIMALE:
        match critere.cle:
            case "glasgow" if c.glasgow is not None and c.glasgow < 14:
                remplis.append(critere)
            case "saturation" if c.saturation is not None and c.saturation < 90:
                remplis.append(critere)
            case "frequence_respiratoire" if c.frequence_respiratoire is not None and (
                c.frequence_respiratoire > 30 or c.frequence_respiratoire < 8
            ):
                remplis.append(critere)
            case "pression_systolique" if c.pression_systolique is not None and (
                c.pression_systolique < 90
            ):
                remplis.append(critere)
            case "frequence_cardiaque" if c.frequence_cardiaque is not None and (
                c.frequence_cardiaque > 130 or c.frequence_cardiaque < 40
            ):
                remplis.append(critere)
            case "signe_gravite" if signe_gravite:
                remplis.append(critere)
    return remplis


def _declencheurs_moderee(c: Constantes) -> list[Critere]:
    """Criteres d'urgence moderee effectivement remplis."""
    remplis = []
    for critere in CRITERES_MODEREE:
        match critere.cle:
            case "saturation" if c.saturation is not None and 90 <= c.saturation <= 94:
                remplis.append(critere)
            case "frequence_respiratoire" if c.frequence_respiratoire is not None and (
                25 <= c.frequence_respiratoire <= 30
            ):
                remplis.append(critere)
            case "pression_systolique" if c.pression_systolique is not None and (
                90 <= c.pression_systolique <= 100
            ):
                remplis.append(critere)
            case "frequence_cardiaque" if c.frequence_cardiaque is not None and (
                110 <= c.frequence_cardiaque <= 130
            ):
                remplis.append(critere)
            case "temperature" if c.temperature is not None and c.temperature >= 39.0:
                remplis.append(critere)
            case "douleur" if c.douleur is not None and c.douleur >= 5:
                remplis.append(critere)
    return remplis


def evaluer_priorite(
    constantes: Constantes, signe_gravite: bool
) -> tuple[NiveauPriorite, list[Critere]]:
    """Deduit le niveau de priorite du tableau clinique.

    Retourne le niveau et les criteres qui l'ont declenche : c'est cette liste
    qui sert de justification dans la reponse attendue du modele.
    """
    if declencheurs := _declencheurs_maximale(constantes, signe_gravite):
        return NiveauPriorite.MAXIMALE, declencheurs
    if declencheurs := _declencheurs_moderee(constantes):
        return NiveauPriorite.MODEREE, declencheurs
    return NiveauPriorite.DIFFEREE, []


# --- Generation des cas ---------------------------------------------------

_CIBLES: Final[tuple[NiveauPriorite, ...]] = (
    NiveauPriorite.MAXIMALE,
    NiveauPriorite.MODEREE,
    NiveauPriorite.DIFFEREE,
)


def _constantes_normales(tirage: random.Random) -> Constantes:
    return Constantes(
        frequence_cardiaque=tirage.randint(62, 95),
        pression_systolique=tirage.randint(112, 138),
        pression_diastolique=tirage.randint(66, 84),
        frequence_respiratoire=tirage.randint(12, 18),
        saturation=tirage.randint(96, 99),
        temperature=round(tirage.uniform(36.3, 37.8), 1),
        glasgow=15,
        douleur=tirage.randint(0, 4),
    )


def _degrader(constantes: Constantes, cible: NiveauPriorite, tirage: random.Random) -> Constantes:
    """Ecarte une ou deux constantes vers la bande visee.

    Le niveau final reste decide par `evaluer_priorite` : cette fonction ne fait
    que produire un tableau clinique plausible pour la bande souhaitee.
    """
    if cible is NiveauPriorite.DIFFEREE:
        return constantes

    if cible is NiveauPriorite.MAXIMALE:
        atteintes = {
            "saturation": lambda: tirage.randint(78, 89),
            "frequence_respiratoire": lambda: tirage.choice(
                [tirage.randint(31, 42), tirage.randint(5, 7)]
            ),
            "pression_systolique": lambda: tirage.randint(64, 89),
            "frequence_cardiaque": lambda: tirage.choice(
                [tirage.randint(131, 165), tirage.randint(32, 39)]
            ),
            "glasgow": lambda: tirage.randint(8, 13),
        }
    else:
        atteintes = {
            "saturation": lambda: tirage.randint(90, 94),
            "frequence_respiratoire": lambda: tirage.randint(25, 30),
            "pression_systolique": lambda: tirage.randint(90, 100),
            "frequence_cardiaque": lambda: tirage.randint(110, 130),
            "temperature": lambda: round(tirage.uniform(39.0, 40.4), 1),
            "douleur": lambda: tirage.randint(5, 7),
        }

    modifiees = dict(vars(constantes))
    for cle in tirage.sample(sorted(atteintes), k=tirage.randint(1, 2)):
        modifiees[cle] = atteintes[cle]()
    if modifiees["pression_systolique"] < modifiees["pression_diastolique"] + 20:
        modifiees["pression_diastolique"] = max(35, modifiees["pression_systolique"] - 30)
    return Constantes(**modifiees)


def _valeur_mesuree(critere: Critere, c: Constantes, langue: str) -> str:
    """Rappelle la valeur relevee a cote du critere, pour une justification concrete."""
    unites = (
        {
            "glasgow": ("Glasgow", ""),
            "saturation": ("SpO2", " %"),
            "frequence_respiratoire": ("FR", "/min"),
            "pression_systolique": ("PAS", " mmHg"),
            "frequence_cardiaque": ("FC", "/min"),
            "temperature": ("T", " °C"),
            "douleur": ("EVA", "/10"),
        }
        if langue == "fr"
        else {
            "glasgow": ("Glasgow", ""),
            "saturation": ("SpO2", "%"),
            "frequence_respiratoire": ("RR", "/min"),
            "pression_systolique": ("SBP", " mmHg"),
            "frequence_cardiaque": ("HR", "/min"),
            "temperature": ("Temp", " °C"),
            "douleur": ("pain", "/10"),
        }
    )
    if critere.cle == "signe_gravite":
        return "signe de gravité rapporté" if langue == "fr" else "red-flag sign reported"
    intitule, unite = unites[critere.cle]
    valeur = getattr(c, critere.cle)
    if critere.cle == "temperature":
        valeur = f"{valeur:.1f}".replace(".", ",") if langue == "fr" else f"{valeur:.1f}"
    return f"{intitule} {valeur}{unite}"


def _formater_constantes(c: Constantes, langue: str) -> str:
    # Les abreviations different d'une langue a l'autre : FC/FR en francais,
    # HR/RR en anglais. Un melange trahirait une traduction bacle.
    fr = langue == "fr"
    pourcent = " %" if fr else "%"
    # Le francais ecrit la decimale avec une virgule.
    temperature = f"{c.temperature:.1f}".replace(".", ",") if fr else f"{c.temperature:.1f}"
    morceaux = [
        f"{'FC' if fr else 'HR'} {c.frequence_cardiaque}/min",
        f"{'PA' if fr else 'BP'} {c.pression_systolique}/{c.pression_diastolique} mmHg",
        f"{'FR' if fr else 'RR'} {c.frequence_respiratoire}/min",
        f"SpO2 {c.saturation}{pourcent}",
        f"{'T' if fr else 'Temp'} {temperature} °C",
        f"Glasgow {c.glasgow}",
        f"{'EVA' if fr else 'pain'} {c.douleur}/10",
    ]
    return ", ".join(morceaux)


_CONDUITE: Final[dict[NiveauPriorite, dict[str, str]]] = {
    NiveauPriorite.MAXIMALE: {
        "fr": "Installation immédiate en salle d'accueil des urgences vitales, "
        "médecin prévenu sans délai, surveillance scopée continue.",
        "en": "Immediate transfer to the resuscitation area, physician alerted without delay, "
        "continuous monitoring.",
    },
    NiveauPriorite.MODEREE: {
        "fr": "Prise en charge médicale dans l'heure, réévaluation des constantes "
        "toutes les 30 minutes, antalgie adaptée.",
        "en": "Medical assessment within the hour, vital signs reassessed every 30 minutes, "
        "appropriate analgesia.",
    },
    NiveauPriorite.DIFFEREE: {
        "fr": "Prise en charge différée sans risque identifié, réévaluation en cas "
        "d'aggravation, orientation possible vers une consultation non programmée.",
        "en": "Deferred care with no identified risk, reassessment if the condition worsens, "
        "may be redirected to an unscheduled consultation.",
    },
}

_LIBELLE_NIVEAU: Final[dict[NiveauPriorite, dict[str, str]]] = {
    NiveauPriorite.MAXIMALE: {"fr": "URGENCE MAXIMALE", "en": "HIGHEST PRIORITY"},
    NiveauPriorite.MODEREE: {"fr": "URGENCE MODÉRÉE", "en": "MODERATE PRIORITY"},
    NiveauPriorite.DIFFEREE: {"fr": "PRISE EN CHARGE DIFFÉRÉE", "en": "DEFERRED CARE"},
}


def _rediger_instruction(
    presentation: Presentation,
    langue: str,
    age: int,
    sexe: str,
    symptomes: list[str],
    antecedents: list[str],
    constantes: Constantes,
    duree: str,
) -> str:
    if langue == "fr":
        return (
            f"Patient de {age} ans, sexe {sexe}.\n"
            f"Motif de recours : {presentation.motif['fr']}, évoluant depuis {duree}.\n"
            f"Symptômes rapportés : {', '.join(symptomes)}.\n"
            f"Antécédents : {', '.join(antecedents)}.\n"
            f"Constantes à l'admission : {_formater_constantes(constantes, 'fr')}.\n\n"
            "Évaluez le niveau de priorité de triage et justifiez votre évaluation."
        )
    return (
        f"{age}-year-old patient, {sexe}.\n"
        f"Presenting complaint: {presentation.motif['en']}, ongoing for {duree}.\n"
        f"Reported symptoms: {', '.join(symptomes)}.\n"
        f"Medical history: {', '.join(antecedents)}.\n"
        f"Vital signs on admission: {_formater_constantes(constantes, 'en')}.\n\n"
        "Assess the triage priority level and justify your assessment."
    )


def rediger_reponse(
    niveau: NiveauPriorite, declencheurs: list[Critere], constantes: Constantes, langue: str
) -> str:
    libelle = _LIBELLE_NIVEAU[niveau][langue]
    conduite = _CONDUITE[niveau][langue]

    if declencheurs:
        lignes = "\n".join(
            f"- {c.libelle[langue]} ({_valeur_mesuree(c, constantes, langue)})"
            for c in declencheurs
        )
        entete = "Éléments déterminants :" if langue == "fr" else "Determining factors:"
    else:
        lignes = (
            "- constantes vitales dans les limites de la normale\n- aucun signe de gravité retrouvé"
            if langue == "fr"
            else "- vital signs within normal limits\n- no red-flag sign identified"
        )
        entete = "Éléments retenus :" if langue == "fr" else "Findings:"

    titre = "Niveau de priorité" if langue == "fr" else "Priority level"
    intitule_conduite = "Conduite recommandée" if langue == "fr" else "Recommended action"
    reserve = (
        "Cette évaluation est une aide à la décision : la validation revient au personnel soignant."
        if langue == "fr"
        else "This assessment is decision support only: validation remains with the clinical staff."
    )
    # Le francais insere une espace avant les deux-points, pas l'anglais.
    sep = " : " if langue == "fr" else ": "
    return (
        f"{titre}{sep}{libelle}.\n\n"
        f"{entete}\n{lignes}\n\n"
        f"{intitule_conduite}{sep}{conduite}\n\n{reserve}"
    )


_DUREES: Final[dict[str, tuple[str, ...]]] = {
    "fr": ("30 minutes", "2 heures", "6 heures", "12 heures", "2 jours", "5 jours"),
    "en": ("30 minutes", "2 hours", "6 hours", "12 hours", "2 days", "5 days"),
}
_SEXES: Final[dict[str, tuple[str, ...]]] = {
    "fr": ("masculin", "féminin"),
    "en": ("male", "female"),
}


def generer_cas(nombre: int, graine: int = 42, part_francais: float = 0.6) -> list[Enregistrement]:
    """Construit `nombre` cas de triage, equilibres entre les trois niveaux."""
    tirage = random.Random(graine)
    enregistrements: list[Enregistrement] = []

    for index in range(nombre):
        presentation = PRESENTATIONS[index % len(PRESENTATIONS)]
        cible = _CIBLES[index % len(_CIBLES)]
        langue = "fr" if tirage.random() < part_francais else "en"

        constantes = _degrader(_constantes_normales(tirage), cible, tirage)
        # Un signe de gravite n'accompagne que les tableaux les plus severes.
        signe_gravite = cible is NiveauPriorite.MAXIMALE and tirage.random() < 0.5

        symptomes = list(
            tirage.sample(
                presentation.symptomes[langue], k=min(3, len(presentation.symptomes[langue]))
            )
        )
        if signe_gravite:
            symptomes.append(tirage.choice(presentation.signes_gravite[langue]))
        antecedents = list(
            tirage.sample(
                presentation.antecedents[langue], k=min(2, len(presentation.antecedents[langue]))
            )
        )

        niveau, declencheurs = evaluer_priorite(constantes, signe_gravite)
        age = tirage.randint(presentation.age_min, presentation.age_max)
        sexe = tirage.choice(_SEXES[langue])
        duree = tirage.choice(_DUREES[langue])

        enregistrements.append(
            Enregistrement(
                id=f"triage_{index:05d}",
                langue=Langue(langue),
                instruction=_rediger_instruction(
                    presentation, langue, age, sexe, symptomes, antecedents, constantes, duree
                ),
                reponse=rediger_reponse(niveau, declencheurs, constantes, langue),
                bloc=Bloc.TRIAGE_STRUCTURE,
                source=SOURCE,
                source_id=f"{presentation.cle}_{index:05d}",
                licence=LICENCE,
                symptomes=symptomes,
                antecedents=antecedents,
                constantes=constantes,
                niveau_priorite=niveau,
                # Bareme non valide cliniquement : la confiance le reflete.
                niveau_confiance=0.7,
                anonymise=True,  # aucun patient reel n'intervient
                transformations=["generation_regles_french"],
                groupe=f"triage_{presentation.cle}_{index:05d}",
            )
        )
    return enregistrements
