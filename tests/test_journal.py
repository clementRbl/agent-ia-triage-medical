"""Verifications du journal d'audit.

Un journal medical ne vaut que si l'on peut prouver qu'il n'a pas ete
retouche. Ces tests reproduisent donc les trois formes d'alteration :
modification, suppression, insertion.
"""

from __future__ import annotations

import json

import pytest

from triage.api.journal import Evenement, Journal, verifier_chaine


@pytest.fixture
def journal(tmp_path, monkeypatch):
    """Journal isole, sans masquage : le masquage a ses propres tests."""
    monkeypatch.setenv("TRIAGE_SANS_ANONYMISATION", "1")
    return Journal(chemin=tmp_path / "journal.jsonl")


def remplir(journal: Journal, nombre: int = 4) -> None:
    for index in range(nombre):
        journal.consigner(f"s{index % 2}", Evenement.QUESTION, {"cle": f"q{index}"})


class TestChainage:
    def test_un_journal_intact_se_verifie(self, journal):
        remplir(journal)
        assert verifier_chaine(journal.chemin) == []

    def test_la_premiere_entree_part_de_la_genese(self, journal):
        entree = journal.consigner("s", Evenement.OUVERTURE, {})
        assert entree.empreinte_precedente == "0" * 64

    def test_chaque_entree_chaine_la_precedente(self, journal):
        premiere = journal.consigner("s", Evenement.OUVERTURE, {})
        seconde = journal.consigner("s", Evenement.QUESTION, {"cle": "motif"})
        assert seconde.empreinte_precedente == premiere.empreinte

    def test_un_journal_absent_est_vide_et_valide(self, tmp_path):
        assert verifier_chaine(tmp_path / "rien.jsonl") == []


class TestDetectionDesAlterations:
    def test_une_entree_modifiee_est_detectee(self, journal):
        remplir(journal)
        lignes = journal.chemin.read_text(encoding="utf-8").splitlines()
        altere = json.loads(lignes[1])
        altere["contenu"] = {"cle": "falsifie"}
        lignes[1] = json.dumps(altere, sort_keys=True, ensure_ascii=False)
        journal.chemin.write_text("\n".join(lignes) + "\n", encoding="utf-8")

        ruptures = verifier_chaine(journal.chemin)
        assert ruptures
        assert ruptures[0].rang == 1

    def test_une_entree_supprimee_est_detectee(self, journal):
        remplir(journal)
        lignes = journal.chemin.read_text(encoding="utf-8").splitlines()
        del lignes[1]
        journal.chemin.write_text("\n".join(lignes) + "\n", encoding="utf-8")
        assert verifier_chaine(journal.chemin)

    def test_une_entree_inseree_est_detectee(self, journal):
        remplir(journal)
        lignes = journal.chemin.read_text(encoding="utf-8").splitlines()
        lignes.insert(2, lignes[0])
        journal.chemin.write_text("\n".join(lignes) + "\n", encoding="utf-8")
        assert verifier_chaine(journal.chemin)

    def test_reordonner_deux_entrees_est_detecte(self, journal):
        remplir(journal)
        lignes = journal.chemin.read_text(encoding="utf-8").splitlines()
        lignes[1], lignes[2] = lignes[2], lignes[1]
        journal.chemin.write_text("\n".join(lignes) + "\n", encoding="utf-8")
        assert verifier_chaine(journal.chemin)


class TestRelecture:
    def test_une_session_se_reconstitue(self, journal):
        remplir(journal, nombre=6)
        assert len(journal.session("s0")) == 3
        assert len(journal.session("s1")) == 3

    def test_une_session_inconnue_ne_renvoie_rien(self, journal):
        remplir(journal)
        assert journal.session("inexistante") == []

    def test_l_horodatage_est_en_temps_universel(self, journal):
        """Un journal d'audit horodate en heure locale devient ininterpretable."""
        entree = journal.consigner("s", Evenement.OUVERTURE, {})
        assert entree.horodatage.endswith("+00:00")


class TestMasquage:
    def test_les_champs_libres_sont_anonymises(self, tmp_path, monkeypatch):
        """Un nom saisi par erreur dans un champ clinique ne doit pas persister."""
        monkeypatch.delenv("TRIAGE_SANS_ANONYMISATION", raising=False)
        journal = Journal(chemin=tmp_path / "journal.jsonl")
        entree = journal.consigner(
            "s", Evenement.REPONSE, {"cle": "motif", "reponse": "Monsieur Alain Dupont, douleur"}
        )
        assert "Dupont" not in entree.contenu["reponse"]
        assert "douleur" in entree.contenu["reponse"]

    def test_les_champs_techniques_ne_sont_pas_touches(self, tmp_path, monkeypatch):
        monkeypatch.delenv("TRIAGE_SANS_ANONYMISATION", raising=False)
        journal = Journal(chemin=tmp_path / "journal.jsonl")
        entree = journal.consigner("s", Evenement.TRIAGE, {"niveau": "maximale", "latence_ms": 42})
        assert entree.contenu == {"niveau": "maximale", "latence_ms": 42}
