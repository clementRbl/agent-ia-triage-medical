"""API de demonstration du triage : questionnaire adaptatif et triage direct.

Deux usages, un seul moteur :

- l'accueil deroule le questionnaire question par question ;
- le SIH, qui detient deja le dossier, poste le tableau clinique complet.

Toute interaction est journalisee. Les acces sont proteges par cle : un
endpoint de triage medical ouvert a tous les vents serait a la fois un risque
clinique et une fuite de donnees de sante.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any, Final

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.security import APIKeyHeader

from triage.api.demo import PAGE
from triage.api.journal import CHEMIN_DEFAUT, Journal, verifier_chaine
from triage.api.moteur import moteur_depuis_environnement
from triage.api.questionnaire import Entretien, Question
from triage.api.schemas import (
    DemandeTriageDirect,
    EtatEntretien,
    IntegriteJournal,
    OuvertureEntretien,
    QuestionSortie,
    ReponseSoumise,
    TriageSortie,
    Version,
)
from triage.api.service import Evaluation, ServiceTriage
from triage.schema import Constantes, Langue

VERSION_SERVICE: Final[str] = "0.1.0"
ENTETE_CLE: Final[str] = "X-Cle-Api"

# Limites d'usage, affichees dans la documentation generee : un utilisateur qui
# ignore ce que l'outil ne sait pas faire lui fera confiance a tort.
LIMITES: Final[str] = (
    "Outil d'aide au tri, POC non certifié dispositif médical. Il ne pose pas de "
    "diagnostic, ne prescrit pas et ne remplace aucune décision soignante. Le "
    "barème utilisé est une transposition simplifiée de l'échelle FRENCH, non "
    "validée par un clinicien. Adulte uniquement : la pédiatrie et l'obstétrique "
    "sont hors périmètre."
)

# Mode d'emploi affiche en tete de la documentation interactive. Une API qu'il
# faut deviner n'est pas utilisable, et le SIH du CHSA doit pouvoir s'y brancher
# sans poser de question.
DESCRIPTION: Final[str] = f"""
⚠️ **{LIMITES}**

---

### Avant tout : s'authentifier

Toutes les routes sauf `/sante` exigent une clé. Cliquez sur **Authorize**
(cadenas, en haut à droite), collez la clé, validez. Elle sera jointe
automatiquement à chaque appel.

`X-Cle-Api` est le **nom de l'en-tête HTTP**, pas la valeur à saisir :

```
X-Cle-Api: la-clé-qui-vous-a-été-remise
```

**Ce qu'est cette clé.** Une chaîne de 43 caractères tirée au sort, partagée
par tous les appelants autorisés. Ce n'est pas un compte : le service ne sait
pas *qui* appelle, seulement que l'appelant la connaît. Elle est remise par
l'administrateur du service et n'apparaît ni dans le code, ni dans le dépôt —
elle est injectée à l'exécution.

**Pourquoi elle existe.** Chaque évaluation occupe un GPU facturé à la seconde.
Et c'est une démonstration de triage médical : une adresse ouverte inviterait
un usage réel par quelqu'un qui n'aurait pas lu les limites ci-dessus.

**Pas de clé ?** `/sante` répond sans authentification, et la page de
démonstration à la racine explique la marche à suivre.

### Deux façons de trier

**1. Le questionnaire adaptatif** — pour un poste d'accueil.

1. `POST /entretiens` → renvoie un `session` et la première question.
2. `POST /entretiens/{{session}}/reponses` → renvoyez la `cle` de la question
   et votre `valeur`, toujours sous forme de chaîne (`"87"`, `"oui"`, `"37,5"`).
   Répétez tant que `termine` vaut `false`.
3. Quand `termine` passe à `true`, la réponse porte le champ `triage`.

Le recueil **s'arrête dès qu'un critère d'urgence maximale est rempli** :
poursuivre ne pourrait plus abaisser le niveau, seulement retarder la prise en
charge.

**2. Le triage direct** — `POST /triage`, pour un système qui détient déjà le
dossier. Des exemples prêts à envoyer sont proposés sous le champ de saisie.

### Lire la réponse

| Champ | Sens |
| --- | --- |
| `niveau` | la priorité retenue, celle qui fait foi |
| `niveau_modele` | ce qu'a annoncé le modèle affiné |
| `niveau_regles` | ce qu'a calculé le barème explicite |
| `escalade` | vrai si le garde-fou a **relevé** la priorité du modèle |
| `criteres` | les critères du barème effectivement remplis |

Le garde-fou n'agit que dans le sens de la sécurité : si le modèle annonce
moins grave que le barème, la priorité est relevée ; s'il annonce plus grave,
sa prudence est conservée.

### Traçabilité

`GET /audit/{{session}}` reconstitue un entretien. `GET /audit` vérifie que le
journal n'a pas été altéré : chaque entrée porte l'empreinte de la précédente.

### Démonstration

Une interface complète est servie à la racine : [`/`](/).
"""


# Declare comme schema de securite plutot que comme simple en-tete : la
# documentation interactive expose alors un bouton « Authorize » ou la cle se
# saisit une fois pour toutes, au lieu d'un champ a retaper a chaque appel.
schema_cle = APIKeyHeader(
    name=ENTETE_CLE,
    auto_error=False,
    scheme_name="Clé de service",
    description=(
        "Collez ici la clé remise par l'administrateur du service — la chaîne "
        "elle-même, pas le nom de l'en-tête. Elle vaut pour toutes les routes "
        "sauf `/sante`, et sera jointe automatiquement aux appels suivants."
    ),
)


def _cles_autorisees() -> set[str]:
    brut = os.environ.get("TRIAGE_CLES_API", "")
    return {cle.strip() for cle in brut.split(",") if cle.strip()}


def verifier_cle(cle: Annotated[str | None, Depends(schema_cle)] = None) -> None:
    """Refuse l'appel si la cle presentee n'est pas connue.

    Sans cle configuree le service reste ouvert : c'est le mode developpement
    local. Le deploiement, lui, en impose une (cf. deploiement/).
    """
    autorisees = _cles_autorisees()
    if not autorisees:
        return
    if cle not in autorisees:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clé d'API absente ou invalide.",
            headers={"WWW-Authenticate": ENTETE_CLE},
        )


def construire_service() -> ServiceTriage:
    chemin = Path(os.environ.get("TRIAGE_JOURNAL", str(CHEMIN_DEFAUT)))
    return ServiceTriage(moteur=moteur_depuis_environnement(), journal=Journal(chemin=chemin))


@asynccontextmanager
async def cycle_de_vie(app: FastAPI) -> Any:
    app.state.service = construire_service()
    yield


app = FastAPI(
    title="Agent d'aide au triage — CHSA",
    # `summary` n'est pas repris : il ferait doublon avec l'avertissement en
    # tete de description, qui est mis en forme et donc plus lisible.
    description=DESCRIPTION,
    version=VERSION_SERVICE,
    lifespan=cycle_de_vie,
)


def service() -> ServiceTriage:
    service_courant: ServiceTriage = app.state.service
    return service_courant


def _question_sortie(question: Question, langue: Langue) -> QuestionSortie:
    return QuestionSortie(
        cle=question.cle,
        libelle=question.texte(langue),
        type_reponse=question.type_reponse,
        minimum=question.minimum,
        maximum=question.maximum,
        unite=question.unite,
        options=list(question.options(langue)),
    )


def _triage_sortie(evaluation: Evaluation) -> TriageSortie:
    return TriageSortie(
        niveau=evaluation.niveau,
        explication=evaluation.explication,
        criteres=evaluation.criteres,
        niveau_modele=evaluation.niveau_modele,
        niveau_regles=evaluation.niveau_regles,
        escalade=evaluation.escalade,
        moteur=evaluation.moteur,
        modele=evaluation.modele,
        latence_ms=evaluation.latence_ms,
    )


def _etat(session: str, entretien: Entretien, courant: ServiceTriage) -> EtatEntretien:
    """Renvoie la question suivante, ou le triage quand le recueil suffit."""
    question = entretien.prochaine_question()
    if question is not None:
        courant.consigner_question(session, question, entretien.langue)
        return EtatEntretien(
            session=session,
            termine=False,
            question=_question_sortie(question, entretien.langue),
            questions_posees=len(entretien.questions_posees),
        )
    evaluation = courant.trier(session, entretien)
    courant.cloturer(session)
    return EtatEntretien(
        session=session,
        termine=True,
        triage=_triage_sortie(evaluation),
        questions_posees=len(entretien.questions_posees),
    )


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def demonstration() -> str:
    """Page de demonstration : le questionnaire adaptatif, deroule pas a pas.

    Non protegee, et sans consequence : elle ne contient aucune donnee et
    n'appelle l'API qu'avec la cle que le visiteur saisit lui-meme. Une racine
    qui repondrait 404 laisserait au contraire penser que le service est en
    panne -- c'est la premiere adresse que l'on essaie.
    """
    return PAGE


@app.get("/sante", tags=["exploitation"])
def sante() -> dict[str, str]:
    """Sonde de vivacite. Volontairement non protegee : l'hebergeur l'appelle."""
    return {"etat": "ok", "version": VERSION_SERVICE}


@app.get("/version", tags=["exploitation"], dependencies=[Depends(verifier_cle)])
def version() -> Version:
    courant = service()
    return Version(
        service=VERSION_SERVICE,
        moteur=courant.moteur.nom,
        modele=getattr(courant.moteur, "modele", "inconnu"),
        revision=os.environ.get("TRIAGE_REVISION"),
    )


@app.post("/entretiens", tags=["triage"], dependencies=[Depends(verifier_cle)])
def ouvrir_entretien(demande: OuvertureEntretien) -> EtatEntretien:
    """Ouvre un entretien et renvoie la premiere question."""
    courant = service()
    session, entretien = courant.ouvrir(demande.langue)
    return _etat(session, entretien, courant)


@app.post("/entretiens/{session}/reponses", tags=["triage"], dependencies=[Depends(verifier_cle)])
def repondre(session: str, reponse: ReponseSoumise) -> EtatEntretien:
    """Enregistre une reponse et renvoie la question suivante, ou le triage."""
    courant = service()
    entretien = courant.entretien(session)
    if entretien is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entretien inconnu ou déjà clôturé.",
        )
    try:
        courant.enregistrer_reponse(session, entretien, reponse.cle, reponse.valeur)
    except ValueError as erreur:
        # L'erreur est renvoyee telle quelle : elle nomme le champ et la borne,
        # ce dont l'agent d'accueil a besoin pour corriger sa saisie.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(erreur)
        ) from erreur
    return _etat(session, entretien, courant)


@app.post("/triage", tags=["triage"], dependencies=[Depends(verifier_cle)])
def triage_direct(demande: DemandeTriageDirect) -> TriageSortie:
    """Trie un dossier complet en une passe, pour integration au SIH."""
    courant = service()
    session, entretien = courant.ouvrir(demande.langue)
    entretien.motif = demande.motif
    entretien.age = demande.age
    entretien.sexe = demande.sexe
    entretien.signe_gravite = demande.signe_gravite
    entretien.antecedents = list(demande.antecedents)
    entretien.constantes = Constantes(**demande.constantes.model_dump())
    evaluation = courant.trier(session, entretien)
    courant.cloturer(session)
    return _triage_sortie(evaluation)


@app.get("/audit/{session}", tags=["audit"], dependencies=[Depends(verifier_cle)])
def audit_session(session: str) -> list[dict[str, Any]]:
    """Reconstitue le deroule complet d'un entretien, pour revue medicale."""
    entrees = service().journal.session(session)
    if not entrees:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Aucune trace pour cette session."
        )
    return [
        {
            "horodatage": e.horodatage,
            "evenement": str(e.evenement),
            "contenu": e.contenu,
            "empreinte": e.empreinte,
        }
        for e in entrees
    ]


@app.get("/audit", tags=["audit"], dependencies=[Depends(verifier_cle)])
def integrite_journal() -> IntegriteJournal:
    """Verifie que le journal n'a pas ete altere depuis son ecriture."""
    journal = service().journal
    ruptures = verifier_chaine(journal.chemin)
    entrees: Iterator[Any] = journal.lire()
    return IntegriteJournal(
        entrees=sum(1 for _ in entrees),
        intact=not ruptures,
        ruptures=[f"entrée {r.rang} : {r.motif}" for r in ruptures],
    )
