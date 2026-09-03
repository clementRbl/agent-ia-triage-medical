"""Regles de priorite et generation des cas de triage.

Le bareme etant la partie la plus sensible du jeu de donnees -- un seuil faux
produit des milliers d'exemples faux -- chaque critere est teste isolement.
"""

from dataclasses import replace

import pytest

from triage.data.triage import (
    PRESENTATIONS,
    PRESENTATIONS_INEDITES,
    evaluer_priorite,
    generer_cas,
)
from triage.schema import Constantes, NiveauPriorite

NORMALES = Constantes(
    frequence_cardiaque=78,
    pression_systolique=125,
    pression_diastolique=75,
    frequence_respiratoire=15,
    saturation=98,
    temperature=36.8,
    glasgow=15,
    douleur=2,
)


def constantes(**ecarts) -> Constantes:
    """Un tableau normal, dont on n'ecarte que la constante testee."""
    return replace(NORMALES, **ecarts)


@pytest.mark.parametrize(
    ("ecart", "critere_attendu"),
    [
        ({"glasgow": 13}, "glasgow"),
        ({"saturation": 89}, "saturation"),
        ({"frequence_respiratoire": 31}, "frequence_respiratoire"),
        ({"frequence_respiratoire": 7}, "frequence_respiratoire"),
        ({"pression_systolique": 89}, "pression_systolique"),
        ({"frequence_cardiaque": 131}, "frequence_cardiaque"),
        ({"frequence_cardiaque": 39}, "frequence_cardiaque"),
    ],
)
def test_criteres_d_urgence_maximale(ecart, critere_attendu):
    niveau, declencheurs = evaluer_priorite(constantes(**ecart), signe_gravite=False)
    assert niveau is NiveauPriorite.MAXIMALE
    assert critere_attendu in {c.cle for c in declencheurs}


def test_signe_de_gravite_seul_suffit():
    niveau, declencheurs = evaluer_priorite(constantes(), signe_gravite=True)
    assert niveau is NiveauPriorite.MAXIMALE
    assert "signe_gravite" in {c.cle for c in declencheurs}


@pytest.mark.parametrize(
    ("ecart", "critere_attendu"),
    [
        ({"saturation": 92}, "saturation"),
        ({"frequence_respiratoire": 27}, "frequence_respiratoire"),
        ({"pression_systolique": 95}, "pression_systolique"),
        ({"frequence_cardiaque": 120}, "frequence_cardiaque"),
        ({"temperature": 39.4}, "temperature"),
        ({"douleur": 6}, "douleur"),
    ],
)
def test_criteres_d_urgence_moderee(ecart, critere_attendu):
    niveau, declencheurs = evaluer_priorite(constantes(**ecart), signe_gravite=False)
    assert niveau is NiveauPriorite.MODEREE
    assert critere_attendu in {c.cle for c in declencheurs}


def test_constantes_normales_donnent_une_prise_en_charge_differee():
    niveau, declencheurs = evaluer_priorite(constantes(), signe_gravite=False)
    assert niveau is NiveauPriorite.DIFFEREE
    assert declencheurs == []


@pytest.mark.parametrize(
    ("valeur", "attendu"),
    [
        (89, NiveauPriorite.MAXIMALE),
        (90, NiveauPriorite.MODEREE),
        (94, NiveauPriorite.MODEREE),
        (95, NiveauPriorite.DIFFEREE),
    ],
)
def test_bornes_exactes_de_la_saturation(valeur, attendu):
    """Les bornes sont la ou se cachent les erreurs de bareme."""
    niveau, _ = evaluer_priorite(constantes(saturation=valeur), signe_gravite=False)
    assert niveau is attendu


def test_la_gravite_l_emporte_sur_la_moderation():
    """Un tableau cumulant les deux bandes doit sortir au niveau le plus grave."""
    niveau, _ = evaluer_priorite(constantes(saturation=85, temperature=39.5), signe_gravite=False)
    assert niveau is NiveauPriorite.MAXIMALE


class TestGeneration:
    def test_volume_demande(self):
        assert len(generer_cas(90)) == 90

    def test_les_trois_niveaux_sont_representes(self):
        niveaux = {c.niveau_priorite for c in generer_cas(90)}
        assert niveaux == set(NiveauPriorite)

    def test_bilingue(self):
        assert {c.langue.value for c in generer_cas(120)} == {"fr", "en"}

    def test_generation_deterministe(self):
        a = [c.reponse for c in generer_cas(30, graine=7)]
        b = [c.reponse for c in generer_cas(30, graine=7)]
        assert a == b

    def test_identifiants_uniques(self):
        cas = generer_cas(200)
        assert len({c.id for c in cas}) == len(cas)
        assert len({c.groupe for c in cas}) == len(cas)

    def test_chaque_cas_porte_le_schema_complet(self):
        for cas in generer_cas(60):
            assert cas.symptomes
            assert cas.antecedents
            assert not cas.constantes.est_vide()
            assert cas.niveau_priorite is not None

    def test_le_niveau_annonce_correspond_aux_regles(self):
        """Le label doit toujours etre la consequence des regles, jamais un choix libre."""
        drapeaux = {
            signe
            for presentation in PRESENTATIONS
            for signes in presentation.signes_gravite.values()
            for signe in signes
        }
        for cas in generer_cas(150):
            attendu, _ = evaluer_priorite(
                cas.constantes, signe_gravite=bool(drapeaux & set(cas.symptomes))
            )
            assert cas.niveau_priorite is attendu, cas.id

    def test_la_reponse_justifie_toujours(self):
        for cas in generer_cas(60):
            entetes = ("Éléments",) if cas.langue.value == "fr" else ("Determining", "Findings")
            assert any(e in cas.reponse for e in entetes), cas.id

    def test_la_reserve_medicale_est_presente(self):
        """Le modele doit apprendre a ne jamais se substituer au soignant."""
        for cas in generer_cas(40):
            marqueur = "aide à la décision" if cas.langue.value == "fr" else "decision support"
            assert marqueur in cas.reponse

    def test_abreviations_coherentes_avec_la_langue(self):
        for cas in generer_cas(80):
            if cas.langue.value == "en":
                assert "HR " in cas.instruction
                assert "FC " not in cas.instruction
            else:
                assert "FC " in cas.instruction


class TestMotifsReserves:
    """Les motifs d'evaluation ne doivent jamais entrer dans l'entrainement."""

    def test_aucun_recouvrement_entre_les_deux_ensembles(self):
        entraines = {p.cle for p in PRESENTATIONS}
        reserves = {p.cle for p in PRESENTATIONS_INEDITES}
        assert not entraines & reserves

    def test_diversite_suffisante(self):
        """Peu de motifs pour beaucoup de cas reviendrait a repeter les memes
        tableaux : le volume ne remplace pas la diversite."""
        assert len(PRESENTATIONS_INEDITES) >= 12

    def test_chaque_motif_est_bilingue(self):
        for presentation in PRESENTATIONS + PRESENTATIONS_INEDITES:
            for champ in (
                presentation.motif,
                presentation.symptomes,
                presentation.signes_gravite,
                presentation.antecedents,
            ):
                assert set(champ) == {"fr", "en"}, presentation.cle
                assert all(champ.values()), presentation.cle

    def test_les_cas_reserves_couvrent_les_trois_niveaux(self):
        cas = generer_cas(
            120, graine=777, presentations=PRESENTATIONS_INEDITES, prefixe="generalisation"
        )
        assert {c.niveau_priorite for c in cas} == set(NiveauPriorite)

    def test_tous_les_motifs_reserves_sont_tires(self):
        cas = generer_cas(
            600, graine=777, presentations=PRESENTATIONS_INEDITES, prefixe="generalisation"
        )
        tires = {c.source_id.rsplit("_", 1)[0] for c in cas}
        assert tires == {p.cle for p in PRESENTATIONS_INEDITES}
