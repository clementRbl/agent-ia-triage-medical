"""Assemblage des jeux : cloisonnement des viviers et qualite des paires DPO."""

import json
from collections import Counter
from pathlib import Path

import pandas as pd
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

LIBELLES = {
    "URGENCE MAXIMALE": NiveauPriorite.MAXIMALE,
    "URGENCE MODÉRÉE": NiveauPriorite.MODEREE,
    "PRISE EN CHARGE DIFFÉRÉE": NiveauPriorite.DIFFEREE,
    "HIGHEST PRIORITY": NiveauPriorite.MAXIMALE,
    "MODERATE PRIORITY": NiveauPriorite.MODEREE,
    "DEFERRED CARE": NiveauPriorite.DIFFEREE,
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
    def test_tous_les_cas_produisent_une_paire(self, paires):
        """Les cas differes etaient auparavant ecartes, ce qui privait le jeu de
        tout contre-exemple de sur-triage."""
        assert len(paires) == 120

    def test_les_deux_sens_d_erreur_sont_representes(self, paires):
        """Un signal unidirectionnel apprend au modele que 'plus haut vaut
        mieux' : c'est ce qui avait fait sur-trier 57 % des cas."""
        sens = Counter(p.type_preference for p in paires)
        assert sens["sous_triage"] > 0
        assert sens["sur_triage"] > 0
        moindre = min(sens["sous_triage"], sens["sur_triage"])
        assert moindre / len(paires) > 0.35, f"répartition déséquilibrée : {sens}"

    def test_une_urgence_maximale_ne_peut_etre_que_minoree(self, paires):
        for paire in paires:
            if "maximale majoré" in paire.motif_rejet:
                raise AssertionError(f"{paire.id} : rien au-dessus de maximale")

    def test_une_prise_en_charge_differee_ne_peut_etre_que_majoree(self, paires):
        for paire in paires:
            if "differee minoré" in paire.motif_rejet:
                raise AssertionError(f"{paire.id} : rien en dessous de differee")

    def test_la_reponse_rejetee_annonce_un_autre_niveau(self, paires):
        def niveau(texte: str) -> NiveauPriorite:
            premiere = texte.split("\n")[0]
            for libelle, valeur in LIBELLES.items():
                if libelle in premiere:
                    return valeur
            raise AssertionError(f"niveau introuvable dans {premiere!r}")

        for paire in paires:
            attendu = niveau(paire.chosen)
            obtenu = niveau(paire.rejected)
            assert obtenu is not attendu, paire.id
            ecart = RANG[obtenu] - RANG[attendu]
            assert abs(ecart) == 1, f"{paire.id} : écart de {ecart} niveaux"
            sens = "sur_triage" if ecart > 0 else "sous_triage"
            assert paire.type_preference == sens, paire.id

    def test_le_sous_triage_declare_des_constantes_normales(self, paires):
        """Un sous-triage reel ne liste pas les criteres de gravite qu'il a
        manques : il affirme un tableau normal."""
        for paire in paires:
            if paire.type_preference != "sous_triage":
                continue
            marqueurs = ("dans les limites de la normale", "within normal limits")
            assert any(m in paire.rejected for m in marqueurs), paire.id

    def test_chosen_et_rejected_different(self, paires):
        for paire in paires:
            assert paire.chosen.strip() != paire.rejected.strip()

    def test_le_motif_de_rejet_precise_le_sens(self, paires):
        for paire in paires:
            assert paire.motif_rejet.startswith(("sous-triage", "sur-triage"))


CORPUS = Path("data/raw/ultramedical_dev.json")
sans_corpus = pytest.mark.skipif(not CORPUS.exists(), reason="corpus UltraMedical absent")


@pytest.mark.integrite
class TestSurCorpusReel:
    """Controles necessitant les corpus bruts, absents d'un depot clone."""

    @sans_corpus
    def test_le_biais_de_longueur_est_exclu(self):
        paires = construire_dpo(60, fichier=CORPUS.name)
        assert paires
        assert all(p.type_preference not in LABELS_EXCLUS for p in paires)

    @sans_corpus
    def test_les_blocs_puisent_dans_des_viviers_disjoints(self):
        sft = bloc_c_socle_anglophone(60, fichier=CORPUS.name)
        dpo = construire_dpo(60, fichier=CORPUS.name)
        assert sft and dpo
        assert not {e.source_id for e in sft} & {p.source_id for p in dpo}


@pytest.mark.integrite
class TestSurJeuxProduits:
    """Memes garanties, verifiees sur les parquet versionnes.

    Ces controles-la tournent en integration continue : ils portent sur le
    livrable lui-meme, pas sur des corpus bruts absents du depot.
    """

    @staticmethod
    def _charger(nom: str):
        chemin = Path("data/processed") / nom
        if not chemin.exists():
            pytest.skip(f"{nom} pas encore produit")
        return pd.read_parquet(chemin)

    def test_le_jeu_sft_compte_bien_cinq_mille_paires(self):
        assert len(self._charger("sft.parquet")) == 5000

    def test_aucun_prompt_de_corpus_ne_sert_au_sft_et_au_dpo(self):
        """Cloisonnement des viviers UltraMedical."""
        sft = self._charger("sft.parquet")
        dpo = self._charger("dpo.parquet")
        prompts_sft = set(sft[sft.source.str.startswith("UltraMedical")].source_id)
        prompts_dpo = set(dpo[dpo.source.str.startswith("UltraMedical")].source_id)
        communs = prompts_sft & prompts_dpo
        assert not communs, sorted(communs)[:5]

    def test_un_cas_partage_reste_dans_le_meme_split(self):
        """Les cas de triage alimentent volontairement les deux jeux : le SFT
        apprend la bonne reponse, le DPO apprend a ecarter le sous-triage du
        meme cas. Ce n'est une fuite que si le cas change de split au passage.
        """
        sft = self._charger("sft.parquet").set_index("source_id").split
        dpo = self._charger("dpo.parquet").set_index("source_id").split
        communs = sft.index.intersection(dpo.index)
        assert len(communs) > 0, "aucun cas partagé : le contrôle serait vide"
        divergents = [
            identifiant for identifiant in communs if sft.loc[identifiant] != dpo.loc[identifiant]
        ]
        assert not divergents, divergents[:5]

    def test_le_jeu_est_bien_bilingue(self):
        langues = self._charger("sft.parquet").langue.value_counts()
        assert set(langues.index) == {"fr", "en"}
        assert langues.min() / langues.sum() > 0.15

    def test_tout_enregistrement_issu_d_un_corpus_est_anonymise(self):
        sft = self._charger("sft.parquet")
        issus_corpus = sft[sft.bloc != "D_triage_structure"]
        assert issus_corpus.anonymise.all()

    def test_les_cas_de_triage_portent_les_trois_niveaux(self):
        sft = self._charger("sft.parquet")
        niveaux = sft[sft.bloc == "D_triage_structure"].niveau_priorite
        assert set(niveaux) == {"maximale", "moderee", "differee"}

    def test_aucune_paire_de_preference_biaisee_par_la_longueur(self):
        assert "length" not in set(self._charger("dpo.parquet").type_preference)
