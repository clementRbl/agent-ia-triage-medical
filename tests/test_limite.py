"""Limite de debit globale des triages."""

from __future__ import annotations

from triage.api.limite import PLAFONDS_TRIAGE, LimiteDebit, Plafond


class Horloge:
    """Horloge manuelle : on avance le temps sans attendre."""

    def __init__(self) -> None:
        self.maintenant = 1000.0

    def __call__(self) -> float:
        return self.maintenant


def test_laisse_passer_jusqu_au_plafond_puis_refuse():
    horloge = Horloge()
    limite = LimiteDebit((Plafond(appels=3, fenetre_s=60),), horloge)
    assert [limite.consommer() for _ in range(3)] == [None, None, None]
    assert limite.consommer() == 60


def test_libere_une_place_quand_le_plus_ancien_appel_sort_de_la_fenetre():
    horloge = Horloge()
    limite = LimiteDebit((Plafond(appels=2, fenetre_s=60),), horloge)
    limite.consommer()
    horloge.maintenant += 30
    limite.consommer()
    horloge.maintenant += 10
    # Le premier appel sort de la fenetre dans 20 s : c'est l'attente annoncee.
    assert limite.consommer() == 20
    horloge.maintenant += 20
    assert limite.consommer() is None


def test_le_plafond_du_jour_s_applique_meme_en_etalant_les_appels():
    horloge = Horloge()
    limite = LimiteDebit(
        (Plafond(appels=10, fenetre_s=60), Plafond(appels=3, fenetre_s=86_400)), horloge
    )
    for _ in range(3):
        assert limite.consommer() is None
        horloge.maintenant += 120
    attente = limite.consommer()
    assert attente is not None
    assert attente > 80_000


def test_un_appel_refuse_ne_compte_pas():
    horloge = Horloge()
    limite = LimiteDebit((Plafond(appels=1, fenetre_s=60),), horloge)
    limite.consommer()
    for _ in range(5):
        limite.consommer()
    horloge.maintenant += 60
    # Les refus n'ont pas prolonge le blocage : la place est libre a 60 s.
    assert limite.consommer() is None


def test_plafonds_du_service():
    # 20 par minute pour une demo a plusieurs, 300 par jour contre un script en boucle
    assert Plafond(appels=20, fenetre_s=60) in PLAFONDS_TRIAGE
    assert Plafond(appels=300, fenetre_s=24 * 60 * 60) in PLAFONDS_TRIAGE
