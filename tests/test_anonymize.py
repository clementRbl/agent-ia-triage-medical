"""Anonymisation : ce qui doit disparaitre et ce qui doit rester."""

import pytest

from triage.data.anonymize import generaliser_grands_ages

CAS = (
    "Monsieur R. âgé de 37 ans, forestier, doit partir au Gabon dans la région "
    "de Lambaréné. Il a consulté le 12 mars 2024 au CHU de Lille. "
    "NIR 1 87 03 59 350 123 45, tél 06 12 34 56 78, r.dupont@mail.fr. "
    "Il présente une dyspnée depuis 3 jours et un signe de Babinski. "
    "Antécédent de maladie de Parkinson."
)


@pytest.fixture(scope="module")
def texte_anonymise(anonymiseur):
    return anonymiseur.anonymiser(CAS, langue="fr").texte


@pytest.mark.parametrize(
    "identifiant",
    ["Monsieur R.", "12 mars 2024", "CHU de Lille", "1 87 03 59 350 123 45", "r.dupont@mail.fr"],
)
def test_identifiants_retires(texte_anonymise, identifiant):
    assert identifiant not in texte_anonymise


@pytest.mark.parametrize(
    "information",
    ["Gabon", "Lambaréné", "37 ans", "depuis 3 jours", "Babinski", "Parkinson", "dyspnée"],
)
def test_information_clinique_preservee(texte_anonymise, information):
    """Le masquage ne doit pas amputer le cas de ce qui fonde le diagnostic."""
    assert information in texte_anonymise


def test_marqueurs_typés(texte_anonymise):
    for marqueur in ("<PATIENT>", "<DATE>", "<NIR>", "<EMAIL>", "<TELEPHONE>"):
        assert marqueur in texte_anonymise


def test_patronyme_complet_apres_civilite(anonymiseur):
    """Regression : "Monsieur V. Joseph" laissait fuiter le patronyme."""
    sortie = anonymiseur.anonymiser("Monsieur V. Joseph est amené aux urgences.", "fr").texte
    assert "Joseph" not in sortie


def test_texte_vide(anonymiseur):
    assert anonymiseur.anonymiser("", "fr").texte == ""


def test_langue_non_supportee(anonymiseur):
    with pytest.raises(ValueError, match="Langue non supportée"):
        anonymiseur.anonymiser("texto", langue="es")


def test_anglais(anonymiseur):
    sortie = anonymiseur.anonymiser("John Smith, 45 years old, reports chest pain.", "en").texte
    assert "John Smith" not in sortie
    assert "chest pain" in sortie


@pytest.mark.parametrize(
    ("entree", "attendu"),
    [
        ("un patient de 37 ans", "un patient de 37 ans"),
        ("une patiente de 92 ans", "une patiente de 90+ ans"),
        ("a man 94 years old", "a man 90+ years old"),
    ],
)
def test_generalisation_des_grands_ages(entree, attendu):
    """L'age reste (determinant clinique) sauf au-dela de 90 ans (re-identifiant)."""
    assert generaliser_grands_ages(entree) == attendu
