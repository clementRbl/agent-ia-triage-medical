"""Regles d'exclusion des faux positifs du detecteur de noms propres."""

import pytest

from triage.data.lexique_medical import est_faux_positif, est_terme_medical


@pytest.mark.parametrize(
    "terme",
    ["Parkinson", "Babinski", "Hémoglobine", "Créatinine", "Cyanose", "Persantine®", "Na", "Sg"],
)
def test_vocabulaire_medical_reconnu(terme):
    assert est_terme_medical(terme)


@pytest.mark.parametrize("nom", ["Dupont", "Brigitte", "Mathilde", "Joseph"])
def test_patronymes_non_confondus(nom):
    assert not est_terme_medical(nom)


def test_eponyme_ecarte_par_le_contexte():
    # "Lyme" n'est pas au lexique : c'est le declencheur "maladie de" qui protege.
    texte = "Le patient présente une maladie de Lyme évoluée."
    debut = texte.index("Lyme")
    assert est_faux_positif(texte, debut, debut + len("Lyme"))


def test_patronyme_conserve_hors_contexte_eponyme():
    texte = "Brigitte se présente aux urgences."
    assert not est_faux_positif(texte, 0, len("Brigitte"))


def test_minuscule_ecartee():
    texte = "une hépatosplénomégalie est retrouvée"
    debut = texte.index("hépatosplénomégalie")
    assert est_faux_positif(texte, debut, debut + len("hépatosplénomégalie"))


def test_initiale_isolee_ecartee():
    texte = "L 70 g/L"
    assert est_faux_positif(texte, 0, 1)
