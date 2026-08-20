"""Tracabilite : chaque etape doit laisser un manifeste verifiable."""

import json

from triage.audit import Manifeste, empreinte_fichier


def test_empreinte_stable(tmp_path):
    a, b = tmp_path / "a.txt", tmp_path / "b.txt"
    a.write_text("cas clinique")
    b.write_text("cas clinique")
    assert empreinte_fichier(a) == empreinte_fichier(b)


def test_empreinte_detecte_modification(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("v1")
    avant = empreinte_fichier(f)
    f.write_text("v2")
    assert empreinte_fichier(f) != avant


def test_manifeste_ecrit_les_empreintes(tmp_path):
    source = tmp_path / "source.jsonl"
    source.write_text('{"id": 1}\n')

    manifeste = Manifeste(etape="test", parametres={"seuil": 0.4})
    manifeste.ajouter_fichier(source, entree=True, nb_lignes=1)
    chemin = manifeste.ecrire(tmp_path / "manifests")

    contenu = json.loads(chemin.read_text())
    assert contenu["etape"] == "test"
    assert contenu["nb_lignes"][str(source)] == 1
    assert len(contenu["empreintes"][str(source)]) == 64
    assert contenu["horodatage"]
    assert contenu["revision_code"]
