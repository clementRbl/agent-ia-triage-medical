"""Journal d'audit des interactions de triage.

Le CHSA demande la tracabilite de « chaque interaction pour les audits
medicaux ». Un fichier de logs ordinaire n'y suffit pas : il se modifie sans
laisser de trace, et un journal medical qu'on peut reecrire apres coup ne
prouve rien.

Chaque entree porte donc l'empreinte de la precedente. Modifier ou supprimer
une ligne ancienne casse la chaine a partir de ce point, et `verifier_chaine`
le detecte. C'est une garantie d'integrite, pas de confidentialite : elle
rend l'alteration *visible*, elle ne l'empeche pas.

Le journal est aussi un traitement de donnees de sante : les champs libres
(motif, antecedents) traversent l'anonymiseur de l'etape 1 avant d'etre
ecrits, pour qu'aucun nom saisi par erreur dans un champ clinique ne se
retrouve conserve sur disque.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Final

# Empreinte conventionnelle de la premiere entree : la chaine doit demarrer
# sur une valeur connue, sinon un journal tronque en tete resterait valide.
GENESE: Final[str] = "0" * 64

CHEMIN_DEFAUT: Final[Path] = Path("outputs/journal_triage.jsonl")


class Evenement(StrEnum):
    """Les moments d'un entretien qui engagent la responsabilite du service."""

    OUVERTURE = "ouverture_session"
    QUESTION = "question_posee"
    REPONSE = "reponse_recue"
    TRIAGE = "triage_rendu"
    ESCALADE = "escalade_securite"
    ERREUR = "erreur"


@dataclass(frozen=True)
class Entree:
    """Une ligne du journal, scellee par l'empreinte de la precedente."""

    horodatage: str
    session: str
    evenement: Evenement
    contenu: dict[str, Any]
    empreinte_precedente: str
    empreinte: str = ""

    def _corps(self) -> dict[str, Any]:
        """Champs scelles, a l'exclusion de l'empreinte elle-meme."""
        return {
            "horodatage": self.horodatage,
            "session": self.session,
            "evenement": str(self.evenement),
            "contenu": self.contenu,
            "empreinte_precedente": self.empreinte_precedente,
        }

    def empreinte_attendue(self) -> str:
        # `sort_keys` et `ensure_ascii=False` fixent une serialisation unique :
        # sans cela deux relectures de la meme entree donneraient deux
        # empreintes differentes et toute verification serait ininterpretable.
        canonique = json.dumps(self._corps(), sort_keys=True, ensure_ascii=False)
        return _empreinte(canonique)

    def sceller(self) -> Entree:
        """Calcule l'empreinte de l'entree a partir de son contenu exact."""
        return replace(self, empreinte=self.empreinte_attendue())


def _empreinte(texte: str) -> str:
    return hashlib.sha256(texte.encode("utf-8")).hexdigest()


def _maintenant() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


@dataclass
class Journal:
    """Journal append-only, sur fichier, sur pour un service multi-thread."""

    chemin: Path = CHEMIN_DEFAUT
    anonymiser: bool = True
    _verrou: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def __post_init__(self) -> None:
        self.chemin.parent.mkdir(parents=True, exist_ok=True)

    def derniere_empreinte(self) -> str:
        if not self.chemin.exists():
            return GENESE
        derniere = GENESE
        for entree in self.lire():
            derniere = entree.empreinte
        return derniere

    def consigner(self, session: str, evenement: Evenement, contenu: dict[str, Any]) -> Entree:
        """Ajoute une entree scellee et la renvoie."""
        charge = _nettoyer(contenu) if self.anonymiser else contenu
        # Le verrou couvre lecture de la queue *et* ecriture : sans lui, deux
        # requetes simultanees chaineraient sur la meme empreinte precedente et
        # produiraient un journal invalide.
        with self._verrou:
            entree = Entree(
                horodatage=_maintenant(),
                session=session,
                evenement=evenement,
                contenu=charge,
                empreinte_precedente=self.derniere_empreinte(),
            ).sceller()
            ligne = json.dumps(asdict(entree), sort_keys=True, ensure_ascii=False)
            with self.chemin.open("a", encoding="utf-8") as fichier:
                fichier.write(ligne + "\n")
                fichier.flush()
                # Sans synchronisation disque, une coupure du conteneur perdrait
                # les dernieres entrees : precisement celles d'un incident.
                os.fsync(fichier.fileno())
        return entree

    def lire(self) -> Iterator[Entree]:
        if not self.chemin.exists():
            return
        with self.chemin.open(encoding="utf-8") as fichier:
            for ligne in fichier:
                if ligne.strip():
                    brut = json.loads(ligne)
                    brut["evenement"] = Evenement(brut["evenement"])
                    yield Entree(**brut)

    def session(self, identifiant: str) -> list[Entree]:
        """Toutes les entrees d'un entretien, pour reconstituer un dossier."""
        return [e for e in self.lire() if e.session == identifiant]


@dataclass(frozen=True)
class Rupture:
    """Une entree dont l'integrite n'est pas verifiee."""

    rang: int
    motif: str


def verifier_chaine(chemin: Path = CHEMIN_DEFAUT) -> list[Rupture]:
    """Rejoue la chaine d'empreintes ; renvoie les ruptures trouvees.

    Une liste vide signifie qu'aucune entree n'a ete modifiee, supprimee ni
    inseree depuis son ecriture.
    """
    journal = Journal(chemin=chemin, anonymiser=False)
    ruptures: list[Rupture] = []
    attendue = GENESE
    for rang, entree in enumerate(journal.lire()):
        if entree.empreinte_precedente != attendue:
            ruptures.append(Rupture(rang, "chaînage rompu : entrée modifiée, supprimée ou insérée"))
        if entree.empreinte != entree.empreinte_attendue():
            ruptures.append(Rupture(rang, "contenu altéré après scellement"))
        attendue = entree.empreinte
    return ruptures


_CLES_LIBRES: Final[frozenset[str]] = frozenset(
    {"motif", "antecedents", "reponse", "explication", "instruction", "question"}
)


def _nettoyer(contenu: dict[str, Any]) -> dict[str, Any]:
    """Masque les identites directes dans les champs de texte libre.

    Import differe : charger les modeles spaCy coute plusieurs secondes et une
    part notable de memoire. Un service demarre pour repondre a des sondes de
    sante n'a aucune raison de les payer.
    """
    from triage.api.anonymisation import masquer

    nettoye: dict[str, Any] = {}
    for cle, valeur in contenu.items():
        if cle in _CLES_LIBRES and isinstance(valeur, str):
            nettoye[cle] = masquer(valeur)
        elif cle in _CLES_LIBRES and isinstance(valeur, list):
            nettoye[cle] = [masquer(v) if isinstance(v, str) else v for v in valeur]
        else:
            nettoye[cle] = valeur
    return nettoye
