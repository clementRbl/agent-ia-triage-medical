"""Assemblage des jeux : cloisonnement des viviers et qualite des paires DPO."""

import json

import pytest

from triage.data.build import (
    LABELS_EXCLUS,
    VIVIERS,
    _vivier,
    bloc_c_socle_anglophone,
    construire_dpo,
    lire_json_array,
    paires_de_triage,
)
from triage.data.triage import generer_cas
from triage.schema import NiveauPriorite

RANG = {
    NiveauPriorite.DIFFEREE: 0,
    NiveauPriorite.MODEREE: 1,
    NiveauPriorite.MAXIMALE: 2,
}


class TestViviers:
    def test_affectation_deterministe(self):
        assert _vivier("MedQA,42") == _vivier("MedQA,42")

    def test_les_trois_viviers_sont_utilises(self):
        obtenus = {_vivier(f"src,{i}") for i in range(2000)}
        assert obtenus == set(VIVIERS)

    def test_repartition_conforme_aux_parts(self):
        echantillon = [_vivier(f"src,{i}") for i in range(20_000)]
        for nom, part in VIVIERS.items():
            observee = echantillon.count(nom) / len(echantillon)
            assert abs(observee - part) < 0.02, f"{nom}: {observee:.3f} attendu {part}"

    def test_un_prompt_n_appartient_qu_a_un_vivier(self):
        """Cloisonnement : c'est ce qui empeche un prompt d'entrainement de
        reapparaitre a l'evaluation."""
        for i in range(500):
            identifiant = f"src,{i}"
            appartenances = [nom for nom in VIVIERS if _vivier(identifiant) == nom]
            assert len(appartenances) == 1


class TestLecteurIncremental:
    def test_equivaut_a_un_chargement_complet(self, tmp_path):
        contenu = [{"a": i, "texte": "é" * 50} for i in range(200)]
        fichier = tmp_path / "jeu.json"
        fichier.write_text(json.dumps(contenu, ensure_ascii=False), encoding="utf-8")
        assert list(lire_json_array(fichier)) == contenu

    def test_tableau_vide(self, tmp_path):
        fichier = tmp_path / "vide.json"
        fichier.write_text("[]", encoding="utf-8")
        assert list(lire_json_array(fichier)) == []

    def test_tableau_indente(self, tmp_path):
        contenu = [{"a": 1}, {"b": 2}]
        fichier = tmp_path / "indente.json"
        fichier.write_text(json.dumps(contenu, indent=2), encoding="utf-8")
        assert list(lire_json_array(fichier)) == contenu


@pytest.fixture(scope="module")
def paires():
    return paires_de_triage(generer_cas(120))


class TestPairesDeTriage:
    def test_les_cas_deja_differes_sont_ecartes(self, paires):
        """Un cas differe ne peut pas etre sous-trie : il n'y a rien en dessous."""
        cas_differes = sum(
            1 for c in generer_cas(120) if c.niveau_priorite is NiveauPriorite.DIFFEREE
        )
        assert len(paires) == 120 - cas_differes

    def test_la_reponse_rejetee_minore_toujours(self, paires):
        libelles = {
            "URGENCE MAXIMALE": NiveauPriorite.MAXIMALE,
            "URGENCE MODÉRÉE": NiveauPriorite.MODEREE,
            "PRISE EN CHARGE DIFFÉRÉE": NiveauPriorite.DIFFEREE,
            "HIGHEST PRIORITY": NiveauPriorite.MAXIMALE,
            "MODERATE PRIORITY": NiveauPriorite.MODEREE,
            "DEFERRED CARE": NiveauPriorite.DIFFEREE,
        }

        def niveau(texte: str) -> NiveauPriorite:
            premiere = texte.split("\n")[0]
            for libelle, valeur in libelles.items():
                if libelle in premiere:
                    return valeur
            raise AssertionError(f"niveau introuvable dans {premiere!r}")

        for paire in paires:
            assert RANG[niveau(paire.rejected)] < RANG[niveau(paire.chosen)], paire.id

    def test_la_reponse_rejetee_est_coherente_avec_elle_meme(self, paires):
        """Le contre-exemple doit etre plausible : un sous-triage reel ne liste
        pas les criteres de gravite qu'il a manques."""
        for paire in paires:
            marqueurs = ("dans les limites de la normale", "within normal limits")
            assert any(m in paire.rejected for m in marqueurs), paire.id

    def test_chosen_et_rejected_different(self, paires):
        for paire in paires:
            assert paire.chosen.strip() != paire.rejected.strip()

    def test_le_motif_de_rejet_est_renseigne(self, paires):
        for paire in paires:
            assert "sous-triage" in paire.motif_rejet


@pytest.mark.integrite
class TestSurCorpusReel:
    """Controles necessitant les corpus telecharges."""

    def test_le_biais_de_longueur_est_exclu(self):
        paires = construire_dpo(60, fichier="ultramedical_dev.json")
        if not paires:
            pytest.skip("corpus UltraMedical absent")
        assert all(p.type_preference not in LABELS_EXCLUS for p in paires)

    def test_sft_et_dpo_ne_partagent_aucun_prompt(self):
        """Le garde-fou central : aucun recouvrement entre entrainement
        supervise et alignement."""
        sft = bloc_c_socle_anglophone(60, fichier="ultramedical_dev.json")
        dpo = construire_dpo(60, fichier="ultramedical_dev.json")
        if not sft or not dpo:
            pytest.skip("corpus UltraMedical absent")
        assert not {e.source_id for e in sft} & {p.source_id for p in dpo}
