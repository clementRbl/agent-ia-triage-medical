"""Campagne de mesure post-deploiement face a la limite de debit du service."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import httpx

RACINE = Path(__file__).resolve().parent.parent


def _charger() -> ModuleType:
    """Importe le script, qui n'est pas un module du paquet."""
    chemin = RACINE / "scripts" / "mesurer_service.py"
    spec = importlib.util.spec_from_file_location("mesurer_service", chemin)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


mesure = _charger()


def _client(reponses: list[httpx.Response]):
    """Client du script branche sur des reponses preparees, sans reseau."""
    restantes = iter(reponses)
    client = mesure.Client("http://service.test", "cle", delai=5.0)
    client.session = httpx.Client(transport=httpx.MockTransport(lambda _: next(restantes)))
    return client


def test_attend_le_delai_annonce_puis_reprend(monkeypatch):
    attentes: list[float] = []
    monkeypatch.setattr(mesure.time, "sleep", attentes.append)
    client = _client(
        [httpx.Response(429, headers={"Retry-After": "7"}), httpx.Response(200, json={})]
    )
    _, reponse = client.triage({})
    assert reponse.status_code == 200
    assert attentes == [7.0]


def test_n_attend_pas_des_heures_quand_le_plafond_du_jour_est_atteint(monkeypatch):
    attentes: list[float] = []
    monkeypatch.setattr(mesure.time, "sleep", attentes.append)
    client = _client([httpx.Response(429, headers={"Retry-After": "50000"})])
    _, reponse = client.triage({})
    assert reponse.status_code == 429
    assert attentes == []


def test_abandonne_apres_quelques_reprises(monkeypatch):
    monkeypatch.setattr(mesure.time, "sleep", lambda _: None)
    refus = [httpx.Response(429, headers={"Retry-After": "1"}) for _ in range(10)]
    _, reponse = _client(refus).triage({})
    # Toujours refuse apres les reprises : compte comme un echec par l'appelant.
    assert reponse.status_code == 429
