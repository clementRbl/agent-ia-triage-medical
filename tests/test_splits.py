"""Decoupage sans fuite entre entrainement et evaluation."""

import pandas as pd
import pytest

from triage.data.splits import (
    detecter_fuites,
    repartir_par_groupe,
    verifier_absence_fuite,
)


@pytest.fixture
def corpus():
    """40 cas cliniques portant chacun 5 questions, comme dans MediQAl."""
    return pd.DataFrame(
        [{"cas": f"cas_{i}", "question": f"q_{i}_{j}"} for i in range(40) for j in range(5)]
    )


def test_aucun_cas_a_cheval_sur_deux_splits(corpus):
    corpus["split"] = repartir_par_groupe(corpus, "cas")
    assert detecter_fuites(corpus, "cas") == []
    verifier_absence_fuite(corpus, "cas")


def test_les_trois_splits_sont_representes(corpus):
    corpus["split"] = repartir_par_groupe(corpus, "cas")
    assert set(corpus["split"]) == {"train", "validation", "test"}


def test_repartition_proche_des_proportions(corpus):
    corpus["split"] = repartir_par_groupe(corpus, "cas")
    part_train = (corpus["split"] == "train").mean()
    assert 0.65 < part_train < 0.95  # 40 groupes : la tolerance est large


def test_affectation_deterministe(corpus):
    a = repartir_par_groupe(corpus, "cas", graine=7)
    b = repartir_par_groupe(corpus, "cas", graine=7)
    pd.testing.assert_series_equal(a, b)


def test_graine_differente_change_la_repartition(corpus):
    a = repartir_par_groupe(corpus, "cas", graine=1)
    b = repartir_par_groupe(corpus, "cas", graine=2)
    assert not a.equals(b)


def test_ajout_de_lignes_ne_redistribue_pas_l_existant(corpus):
    """Une affectation par empreinte reste stable quand le corpus grandit."""
    avant = repartir_par_groupe(corpus, "cas")
    agrandi = pd.concat(
        [corpus, pd.DataFrame([{"cas": "cas_99", "question": "q"}])], ignore_index=True
    )
    apres = repartir_par_groupe(agrandi, "cas")
    pd.testing.assert_series_equal(avant, apres.iloc[: len(corpus)])


def test_fuite_detectee(corpus):
    corpus["split"] = repartir_par_groupe(corpus, "cas")
    # On force un cas a cheval, comme le ferait un decoupage ligne a ligne.
    indices = corpus.index[corpus["cas"] == "cas_0"]
    corpus.loc[indices[0], "split"] = "train"
    corpus.loc[indices[1], "split"] = "test"

    fuites = detecter_fuites(corpus, "cas")
    assert len(fuites) == 1
    assert fuites[0].groupe == "cas_0"
    with pytest.raises(ValueError, match="Fuite entre les jeux"):
        verifier_absence_fuite(corpus, "cas")


def test_lignes_sans_groupe_ne_fuient_pas():
    donnees = pd.DataFrame({"cas": [None] * 20, "question": list(range(20))})
    donnees["split"] = repartir_par_groupe(donnees, "cas")
    assert detecter_fuites(donnees, "cas") == []


def test_proportions_invalides(corpus):
    with pytest.raises(ValueError, match="somme"):
        repartir_par_groupe(corpus, "cas", proportions={"train": 0.5, "test": 0.2})


def test_colonne_de_groupe_absente(corpus):
    with pytest.raises(KeyError, match="absente"):
        repartir_par_groupe(corpus, "inexistante")
