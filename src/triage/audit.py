"""Tracabilite des transformations de donnees.

Exigence de l'etape 1 : "conserver une trace de chaque transformation de
donnees (auditabilite)". Chaque etape du pipeline ecrit un manifeste JSON
horodate contenant les empreintes d'entree et de sortie.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

MANIFESTES = Path("data/manifests")


def empreinte_fichier(chemin: Path) -> str:
    """SHA-256 d'un fichier, lu par blocs pour supporter les gros corpus."""
    h = hashlib.sha256()
    with chemin.open("rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


def _revision_code() -> str:
    """Revision git courante, pour relier un artefact au code qui l'a produit."""
    try:
        rev = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return rev.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "inconnue"


@dataclass
class Manifeste:
    """Trace d'une etape du pipeline."""

    etape: str
    entrees: list[str] = field(default_factory=list)
    sorties: list[str] = field(default_factory=list)
    empreintes: dict[str, str] = field(default_factory=dict)
    nb_lignes: dict[str, int] = field(default_factory=dict)
    parametres: dict[str, Any] = field(default_factory=dict)
    statistiques: dict[str, Any] = field(default_factory=dict)
    horodatage: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    revision_code: str = field(default_factory=_revision_code)

    def ajouter_fichier(self, chemin: Path, *, entree: bool, nb_lignes: int | None = None) -> None:
        cible = self.entrees if entree else self.sorties
        cible.append(str(chemin))
        if chemin.exists():
            self.empreintes[str(chemin)] = empreinte_fichier(chemin)
        if nb_lignes is not None:
            self.nb_lignes[str(chemin)] = nb_lignes

    def ecrire(self, dossier: Path = MANIFESTES) -> Path:
        dossier.mkdir(parents=True, exist_ok=True)
        horo = self.horodatage.replace(":", "").replace("-", "")[:15]
        chemin = dossier / f"{self.etape}_{horo}.json"
        chemin.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")
        return chemin
