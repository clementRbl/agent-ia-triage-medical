"""Metriques de triage : distinguer sous-triage et sur-triage."""

import pytest

from triage.schema import NiveauPriorite
from triage.training.evaluation import comparer, extraire_niveau

MAX = NiveauPriorite.MAXIMALE
MOD = NiveauPriorite.MODEREE
DIF = NiveauPriorite.DIFFEREE


@pytest.mark.parametrize(
    ("texte", "attendu"),
    [
        ("Niveau de priorité : URGENCE MAXIMALE.\n\nÉléments…", MAX),
        ("Niveau de priorité : URGENCE MODÉRÉE.", MOD),
        ("Niveau de priorité : PRISE EN CHARGE DIFFÉRÉE.", DIF),
        ("Priority level: HIGHEST PRIORITY.", MAX),
        ("Priority level: MODERATE PRIORITY.", MOD),
        ("Priority level: DEFERRED CARE.", DIF),
        ("urgence maximale sans majuscules", MAX),
        ("URGENCE MODEREE sans accent", MOD),
    ],
)
def test_extraction_du_niveau(texte, attendu):
    assert extraire_niveau(texte) is attendu


@pytest.mark.parametrize("texte", ["", "Le patient va bien.", "Réponse hors format."])
def test_absence_de_niveau(texte):
    """Une reponse sans niveau ne doit pas etre rattachee a une classe par defaut."""
    assert extraire_niveau(texte) is None


class TestComparaison:
    def test_predictions_parfaites(self):
        r = comparer([MAX, MOD, DIF], [MAX, MOD, DIF], "parfait")
        assert r.exactitude == 1.0
        assert r.taux_sous_triage == 0.0
        assert r.taux_sur_triage == 0.0

    def test_sous_triage_compte_a_part(self):
        """Annoncer 'différé' sur un cas critique est l'erreur dangereuse."""
        r = comparer([MAX, MAX], [DIF, MOD], "sous")
        assert r.sous_triages == 2
        assert r.sur_triages == 0
        assert r.taux_sous_triage == 1.0

    def test_sur_triage_compte_a_part(self):
        r = comparer([DIF, MOD], [MAX, MAX], "sur")
        assert r.sur_triages == 2
        assert r.sous_triages == 0

    def test_les_deux_erreurs_ne_se_compensent_pas(self):
        """Un sur-triage ne rachete pas un sous-triage : les taux restent distincts."""
        r = comparer([MAX, DIF], [DIF, MAX], "mixte")
        assert r.taux_sous_triage == 0.5
        assert r.taux_sur_triage == 0.5
        assert r.exactitude == 0.0

    def test_reponse_hors_format_isolee(self):
        r = comparer([MAX, MOD], [None, MOD], "format")
        assert r.sans_niveau == 1
        assert r.exacts == 1
        assert r.sous_triages == 0  # ne bascule pas dans une classe d'erreur

    def test_matrice_de_confusion(self):
        r = comparer([MAX, MAX, MOD], [MAX, DIF, MOD], "matrice")
        assert r.matrice["maximale"]["maximale"] == 1
        assert r.matrice["maximale"]["differee"] == 1
        assert r.matrice["moderee"]["moderee"] == 1

    def test_exemples_de_sous_triage_conserves(self):
        r = comparer([MAX], [DIF], "exemples", instructions=["Patient de 70 ans, SpO2 82 %"])
        assert len(r.exemples_sous_triage) == 1
        assert r.exemples_sous_triage[0]["attendu"] == "maximale"
        assert "SpO2" in r.exemples_sous_triage[0]["instruction"]

    def test_longueurs_incoherentes_refusees(self):
        with pytest.raises(ValueError, match="longueurs incohérentes"):
            comparer([MAX, MOD], [MAX], "erreur")

    def test_jeu_vide(self):
        r = comparer([], [], "vide")
        assert r.exactitude == 0.0
        assert r.taux_sous_triage == 0.0
