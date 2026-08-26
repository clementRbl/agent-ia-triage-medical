"""Serialisation des configurations d'entrainement.

Un manifeste s'ecrit apres l'entrainement : une erreur de serialisation y perd
la trace d'audit d'un run de quarante minutes.
"""

import json
from pathlib import Path

from triage.training.config import ConfigDPO, ConfigSFT


def test_config_sft_serialisable():
    json.dumps(ConfigSFT().en_dict())


def test_config_dpo_serialisable():
    json.dumps(ConfigDPO().en_dict())


def test_tous_les_chemins_sont_convertis():
    """Regression : un champ Path ajoute plus tard faisait echouer le manifeste."""
    for config in (ConfigSFT(), ConfigDPO()):
        for cle, valeur in config.en_dict().items():
            assert not isinstance(valeur, Path), f"{type(config).__name__}.{cle}"


def test_les_tuples_deviennent_des_listes():
    assert isinstance(ConfigSFT().en_dict()["modules_cibles"], list)


def test_le_lot_effectif_combine_lot_et_accumulation():
    config = ConfigSFT(taille_lot=2, accumulation=8)
    assert config.lot_effectif == 16


def test_le_dpo_reduit_le_lot_et_double_l_accumulation():
    """Le DPO concatene les deux branches : le lot doit rester a 1."""
    config = ConfigDPO()
    assert config.taille_lot == 1
    assert config.lot_effectif == ConfigSFT().lot_effectif
