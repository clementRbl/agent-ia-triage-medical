"""Verifications des intervalles de confiance et du test apparie.

Les valeurs de reference sont calculables a la main : c'est le seul moyen de
distinguer une formule juste d'une formule qui *semble* produire des nombres
plausibles.
"""

from __future__ import annotations

import pytest

from triage.training.statistiques import (
    cas_necessaires,
    p_valeur_appariee,
    wilson,
)


class TestWilson:
    def test_zero_succes_ne_donne_pas_de_borne_negative(self) -> None:
        """C'est tout l'interet de Wilson : Wald descendrait sous zero."""
        intervalle = wilson(0, 40)
        assert intervalle.borne_basse == 0.0
        assert intervalle.borne_haute == pytest.approx(0.0876, abs=1e-3)

    def test_taux_maximal_ne_depasse_pas_un(self) -> None:
        intervalle = wilson(40, 40)
        assert intervalle.borne_haute == 1.0
        assert intervalle.borne_basse == pytest.approx(0.9124, abs=1e-3)

    def test_valeur_de_reference(self) -> None:
        """5 sur 40 : intervalle publie [5,45 % ; 26,11 %]."""
        intervalle = wilson(5, 40)
        assert intervalle.proportion == pytest.approx(0.125)
        assert intervalle.borne_basse == pytest.approx(0.0545, abs=1e-3)
        assert intervalle.borne_haute == pytest.approx(0.2611, abs=1e-3)

    def test_l_intervalle_se_resserre_quand_l_effectif_grandit(self) -> None:
        """La raison meme d'avoir elargi le jeu d'evaluation."""
        petit = wilson(5, 40)
        grand = wilson(25, 200)
        assert petit.proportion == pytest.approx(grand.proportion)
        assert grand.demi_largeur < petit.demi_largeur / 2

    def test_total_nul(self) -> None:
        intervalle = wilson(0, 0)
        assert intervalle.proportion == 0.0
        assert (intervalle.borne_basse, intervalle.borne_haute) == (0.0, 0.0)

    def test_succes_superieur_au_total_est_refuse(self) -> None:
        with pytest.raises(ValueError):
            wilson(41, 40)


class TestCasNecessaires:
    def test_precision_de_cinq_points(self) -> None:
        """Le dimensionnement qui a fixe la taille du jeu de generalisation."""
        assert cas_necessaires(0.05) == 385

    def test_un_taux_attendu_extreme_reduit_l_effectif(self) -> None:
        """La variance est maximale a 50 % : c'est l'hypothese prudente."""
        assert cas_necessaires(0.05, taux_attendu=0.1) < cas_necessaires(0.05)

    def test_demi_largeur_invalide(self) -> None:
        with pytest.raises(ValueError):
            cas_necessaires(0.0)


class TestPValeurAppariee:
    def test_sans_discordance_aucun_ecart_mesurable(self) -> None:
        assert p_valeur_appariee(0, 0) == 1.0

    def test_deux_paires_discordantes_ne_prouvent_rien(self) -> None:
        """Le cas rencontre sur le jeu initial : p = 0,50."""
        assert p_valeur_appariee(2, 0) == pytest.approx(0.5)

    def test_symetrie(self) -> None:
        assert p_valeur_appariee(3, 12) == pytest.approx(p_valeur_appariee(12, 3))

    def test_forte_asymetrie_devient_significative(self) -> None:
        assert p_valeur_appariee(12, 1) < 0.05

    def test_effectifs_negatifs_refuses(self) -> None:
        with pytest.raises(ValueError):
            p_valeur_appariee(-1, 3)
