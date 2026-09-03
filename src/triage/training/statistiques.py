"""Intervalles de confiance et comparaison appariee de deux modeles.

Un taux d'exactitude sans intervalle ne dit pas s'il est mesure sur 40 cas ou
sur 600 : c'est pourtant ce qui decide si un ecart entre deux modeles est reel
ou du au hasard du tirage. Ces fonctions sont isolees de l'evaluation pour
etre verifiables independamment des poids du modele.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

# Quantile normal a 97,5 % : borne bilaterale a 95 %.
Z_95: Final[float] = 1.959963985


@dataclass(frozen=True)
class Intervalle:
    """Proportion observee accompagnee de son intervalle de confiance."""

    succes: int
    total: int
    borne_basse: float
    borne_haute: float

    @property
    def proportion(self) -> float:
        return self.succes / self.total if self.total else 0.0

    @property
    def demi_largeur(self) -> float:
        """Precision de la mesure, en points de pourcentage / 100."""
        return (self.borne_haute - self.borne_basse) / 2

    def __str__(self) -> str:
        return (
            f"{100 * self.proportion:5.2f} %  "
            f"[{100 * self.borne_basse:5.2f} % a {100 * self.borne_haute:5.2f} %]  "
            f"({self.succes}/{self.total})"
        )


def wilson(succes: int, total: int, z: float = Z_95) -> Intervalle:
    """Intervalle de Wilson, fiable sur petits effectifs et taux extremes.

    L'intervalle normal (Wald) produit des bornes negatives quand le taux
    approche zero — exactement le regime du sous-triage critique, qu'on espere
    proche de 0 %. Wilson reste dans [0, 1] et conserve sa couverture.
    """
    if total <= 0:
        return Intervalle(0, 0, 0.0, 0.0)
    if not 0 <= succes <= total:
        raise ValueError(f"{succes} succes pour {total} essais")

    proportion = succes / total
    denominateur = 1 + z**2 / total
    centre = (proportion + z**2 / (2 * total)) / denominateur
    ecart = (
        z * math.sqrt(proportion * (1 - proportion) / total + z**2 / (4 * total**2)) / denominateur
    )
    return Intervalle(succes, total, max(0.0, centre - ecart), min(1.0, centre + ecart))


def cas_necessaires(demi_largeur_visee: float, taux_attendu: float = 0.5) -> int:
    """Effectif requis pour atteindre une precision donnee.

    Sert a dimensionner un jeu d'evaluation *avant* de le produire plutot qu'a
    constater apres coup que l'intervalle est trop large.
    """
    if not 0 < demi_largeur_visee < 1:
        raise ValueError("la demi-largeur visee doit etre dans ]0, 1[")
    return math.ceil(Z_95**2 * taux_attendu * (1 - taux_attendu) / demi_largeur_visee**2)


def p_valeur_appariee(gagne_a: int, gagne_b: int) -> float:
    """Test binomial exact bilateral sur les paires discordantes (McNemar).

    Les deux modeles repondent aux memes cas : les traiter comme deux
    echantillons independants gaspille cette information. Seuls les cas ou ils
    divergent portent un signal ; sous l'hypothese nulle, ils se repartissent a
    pile ou face entre les deux modeles.
    """
    if gagne_a < 0 or gagne_b < 0:
        raise ValueError("les effectifs discordants ne peuvent pas etre negatifs")
    discordants = gagne_a + gagne_b
    if discordants == 0:
        return 1.0
    minimum = min(gagne_a, gagne_b)
    queue = sum(math.comb(discordants, i) for i in range(minimum + 1)) / 2**discordants
    return min(1.0, 2 * queue)
