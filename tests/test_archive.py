"""Archive de rendu : nommage impose par la plateforme et exclusions."""

import importlib.util
import re
import sys
import zipfile
from pathlib import Path
from types import ModuleType

import pytest

RACINE = Path(__file__).resolve().parent.parent


def _charger() -> ModuleType:
    """Importe le script, qui n'est pas un module du paquet."""
    chemin = RACINE / "scripts" / "construire_archive.py"
    spec = importlib.util.spec_from_file_location("construire_archive", chemin)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


archive = _charger()


# La plateforme rejette un depot mal nomme sans dire lequel des cinq fichiers
# est en cause : le motif est donc verifie ici plutot qu'au moment du rendu.
MOTIF = re.compile(r"^Reboul_Clement_[1-5]_[A-Za-z]+_082026$")


def test_periode_est_le_mois_de_demarrage() -> None:
    """`mmaaaa` designe le demarrage du projet, pas la date de rendu."""
    assert archive.PERIODE == "082026"


def test_les_quatre_livrables_zippes_respectent_le_nommage() -> None:
    noms = [
        f"{archive.PREFIXE}_{suffixe}_{archive.PERIODE}"
        for suffixe, *_ in archive._livrables(RACINE)
    ]
    assert len(noms) == 4
    for nom in noms:
        assert MOTIF.match(nom), nom


def test_le_rapport_complete_la_serie_des_cinq() -> None:
    """Le cinquieme livrable est le PDF, deja nomme par sa chaine de fabrication."""
    rapport = RACINE / "rapport" / f"{archive.PREFIXE}_5_Rapport_{archive.PERIODE}.pdf"
    assert MOTIF.match(rapport.stem)


@pytest.mark.parametrize("exclu", ["ref", "__pycache__"])
def test_les_dossiers_exclus_ne_sont_jamais_collectes(tmp_path: Path, exclu: str) -> None:
    (tmp_path / "garde.txt").write_text("utile")
    (tmp_path / exclu).mkdir()
    (tmp_path / exclu / "jete.txt").write_text("inutile")
    (tmp_path / "sous" / exclu).mkdir(parents=True)
    (tmp_path / "sous" / exclu / "jete.txt").write_text("inutile")

    collectes = [f.name for f in archive._fichiers(tmp_path)]

    assert collectes == ["garde.txt"]


def test_le_zip_porte_les_chemins_prefixes_et_les_notes(tmp_path: Path) -> None:
    source = tmp_path / "source"
    (source / "dossier").mkdir(parents=True)
    (source / "dossier" / "fichier.txt").write_text("contenu")
    cible = tmp_path / "livrable.zip"

    archive._ecrire_zip(cible, archive._dossier(source, "prefixe"), {"LISEZ-MOI.md": "note"})

    with zipfile.ZipFile(cible) as zf:
        assert sorted(zf.namelist()) == ["LISEZ-MOI.md", "prefixe/dossier/fichier.txt"]
        assert zf.read("LISEZ-MOI.md").decode() == "note"


def test_la_note_du_modele_renvoie_au_depot_publie() -> None:
    """Les poids sont fournis, mais le modele de base n'est pas redistribue."""
    assert archive.MODELE_HF in archive.NOTE_MODELE
    assert "Qwen/Qwen3-1.7B-Base" in archive.NOTE_MODELE


def test_la_note_de_l_endpoint_ne_contient_aucune_cle() -> None:
    """La cle d'acces est remise separement : elle n'entre pas dans l'archive."""
    assert archive.ENDPOINT in archive.NOTE_ENDPOINT
    assert "X-Cle-Api" in archive.NOTE_ENDPOINT
    assert not re.search(r"[A-Za-z0-9_-]{40,}", archive.NOTE_ENDPOINT)
