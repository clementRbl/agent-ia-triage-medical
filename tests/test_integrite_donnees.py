"""Controles d'integrite executes sur les artefacts reels, pas sur des fixtures.

Ces tests portent le marqueur `integrite` et tournent dans un job dedie de la
CI. Ils sont ignores tant que l'artefact concerne n'a pas ete produit, ce qui
laisse la CI verte sur un depot fraichement clone.
"""

import json
from pathlib import Path

import pandas as pd
import pytest

from triage.audit import empreinte_fichier
from triage.data.splits import verifier_absence_fuite

pytestmark = pytest.mark.integrite

RACINE = Path(__file__).resolve().parents[1]
MANIFESTES = RACINE / "data" / "manifests"
TRAITE = RACINE / "data" / "processed"


def _manifestes_avec_empreintes() -> list[Path]:
    return [
        f
        for f in sorted(MANIFESTES.glob("*.json"))
        if json.loads(f.read_text(encoding="utf-8")).get("empreintes")
    ]


@pytest.mark.parametrize("manifeste", _manifestes_avec_empreintes(), ids=lambda p: p.name)
def test_empreintes_du_manifeste_correspondent_aux_fichiers(manifeste):
    """Un artefact encore present doit correspondre a l'empreinte enregistree."""
    contenu = json.loads(manifeste.read_text(encoding="utf-8"))
    verifies = 0
    for chemin_texte, empreinte in contenu["empreintes"].items():
        chemin = RACINE / chemin_texte
        if not chemin.exists():
            continue  # artefact volumineux non versionne
        assert empreinte_fichier(chemin) == empreinte, (
            f"{chemin_texte} a été modifié depuis la production du manifeste "
            f"{manifeste.name} : la trace d'audit ne vaut plus."
        )
        verifies += 1
    if verifies == 0:
        pytest.skip("aucun artefact référencé n'est présent localement")


@pytest.mark.parametrize(
    ("fichier", "colonne_groupe"),
    [("sft.parquet", "cas_source"), ("dpo.parquet", "prompt_id")],
)
def test_absence_de_fuite_entre_les_jeux(fichier, colonne_groupe):
    """Garde-fou du cahier des charges : jamais un meme groupe des deux cotes."""
    chemin = TRAITE / fichier
    if not chemin.exists():
        pytest.skip(f"{fichier} pas encore produit")
    donnees = pd.read_parquet(chemin)
    verifier_absence_fuite(donnees, colonne_groupe)


def test_le_rapport_de_controle_du_masquage_reste_sous_le_seuil():
    """Seuil d'acceptation : moins de 1 % de textes avec PII residuelle."""
    rapport = MANIFESTES / "qc_anonymisation_mediqal_oeq.json"
    if not rapport.exists():
        pytest.skip("contrôle qualité pas encore exécuté")
    contenu = json.loads(rapport.read_text(encoding="utf-8"))
    assert contenu["taux_residuel"] < 0.01, (
        f"taux de PII résiduelle trop élevé : {100 * contenu['taux_residuel']:.2f} %"
    )
