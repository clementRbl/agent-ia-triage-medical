"""Verifications du questionnaire adaptatif.

Ce qui est teste ici n'est pas « le questionnaire pose des questions » mais
les deux proprietes dont depend sa securite : il s'arrete sur une regle
explicite, et il s'arrete *tot* quand le patient est grave.
"""

from __future__ import annotations

import pytest

from triage.api.questionnaire import (
    QUESTIONS_CONSTANTES,
    SIGNES_GENERAUX,
    Entretien,
    TypeReponse,
    signes_a_rechercher,
)
from triage.data.triage import PRESENTATIONS, composer_instruction
from triage.schema import Constantes, Langue, NiveauPriorite


def repondre_jusqu_a(entretien: Entretien, cle: str, limite: int = 20) -> None:
    """Deroule le questionnaire avec des reponses neutres jusqu'a une cle."""
    from triage.api.service import appliquer_reponse

    neutres = {
        "motif": "douleur thoracique",
        "age": "60",
        "sexe": "masculin",
        "signe_gravite": "non",
        "glasgow": "15",
        "saturation": "98",
        "frequence_respiratoire": "16",
        "pression_systolique": "130",
        "pression_diastolique": "80",
        "frequence_cardiaque": "75",
        "temperature": "37,0",
        "douleur": "2",
        "antecedents": "aucun",
    }
    for _ in range(limite):
        question = entretien.prochaine_question()
        if question is None or question.cle == cle:
            return
        appliquer_reponse(entretien, question.cle, neutres[question.cle])
    raise AssertionError(f"question {cle!r} jamais atteinte")


class TestAdaptativite:
    def test_le_depistage_depend_du_motif(self):
        """On ne demande pas la cyanose a un patient venu pour une entorse."""
        thorax = signes_a_rechercher("douleur thoracique", Langue.FR)
        respiratoire = signes_a_rechercher("dyspnée", Langue.FR)
        assert thorax != respiratoire
        assert "cyanose" in respiratoire

    def test_un_motif_inconnu_retombe_sur_les_signes_generaux(self):
        """Le champ est libre : il faut un depistage valable en toute situation."""
        assert signes_a_rechercher("sensation bizarre", Langue.FR) == SIGNES_GENERAUX["fr"]

    def test_le_depistage_existe_dans_les_deux_langues(self):
        for presentation in PRESENTATIONS:
            motif_en = presentation.motif["en"]
            assert signes_a_rechercher(motif_en, Langue.EN)

    def test_la_premiere_question_est_le_motif(self):
        question = Entretien().prochaine_question()
        assert question is not None
        assert question.cle == "motif"
        assert question.type_reponse is TypeReponse.TEXTE


class TestArretPrecoce:
    def test_un_signe_de_gravite_clot_le_recueil(self):
        """Poursuivre ne pourrait plus abaisser le niveau : cela ne ferait que retarder."""
        entretien = Entretien(motif="douleur thoracique", age=60, sexe="masculin")
        repondre_jusqu_a(entretien, "signe_gravite")
        from triage.api.service import appliquer_reponse

        appliquer_reponse(entretien, "signe_gravite", "oui")
        assert entretien.prochaine_question() is None
        assert entretien.niveau_regles()[0] is NiveauPriorite.MAXIMALE

    def test_une_constante_critique_clot_le_recueil(self):
        entretien = Entretien(motif="dyspnée", age=70, sexe="féminin", signe_gravite=False)
        from triage.api.service import appliquer_reponse

        appliquer_reponse(entretien, "glasgow", "15")
        appliquer_reponse(entretien, "saturation", "86")
        assert entretien.prochaine_question() is None
        assert entretien.niveau_regles()[0] is NiveauPriorite.MAXIMALE

    def test_un_tableau_rassurant_va_jusqu_aux_antecedents(self):
        entretien = Entretien()
        repondre_jusqu_a(entretien, "antecedents")
        question = entretien.prochaine_question()
        assert question is not None
        assert question.cle == "antecedents"

    def test_le_questionnaire_se_termine_toujours(self):
        entretien = Entretien()
        repondre_jusqu_a(entretien, "___jamais___", limite=30)


class TestOrdreDesQuestions:
    def test_les_constantes_vont_du_plus_au_moins_discriminant(self):
        """Glasgow et SpO2 tranchent seuls ; la douleur ne conclut jamais."""
        cles = [q.cle for q in QUESTIONS_CONSTANTES]
        assert cles[0] == "glasgow"
        assert cles[1] == "saturation"
        assert cles[-1] == "douleur"

    def test_chaque_question_chiffree_porte_ses_bornes(self):
        for question in QUESTIONS_CONSTANTES:
            assert question.minimum is not None
            assert question.maximum is not None
            assert question.minimum < question.maximum


class TestFideliteDuPrompt:
    def test_le_prompt_servi_a_le_format_de_l_entrainement(self):
        """Une derive de mise en forme ferait chuter le modele sans alerte."""
        entretien = Entretien(
            langue=Langue.FR,
            motif="douleur thoracique",
            age=64,
            sexe="masculin",
            signe_gravite=False,
            antecedents=["hypertension artérielle"],
            constantes=Constantes(
                frequence_cardiaque=88,
                pression_systolique=140,
                pression_diastolique=85,
                frequence_respiratoire=18,
                saturation=97,
                temperature=37.2,
                glasgow=15,
                douleur=4,
            ),
        )
        attendu = composer_instruction(
            langue="fr",
            age=64,
            sexe="masculin",
            motif="douleur thoracique",
            symptomes=[],
            antecedents=["hypertension artérielle"],
            constantes=entretien.constantes,
        )
        assert entretien.instruction() == attendu
        assert entretien.instruction().startswith("Patient de 64 ans, sexe masculin.")
        assert entretien.instruction().endswith(
            "Évaluez le niveau de priorité de triage et justifiez votre évaluation."
        )

    def test_les_constantes_manquantes_sont_omises_et_non_inventees(self):
        entretien = Entretien(
            motif="céphalée", age=30, sexe="féminin", constantes=Constantes(saturation=99)
        )
        instruction = entretien.instruction()
        assert "SpO2 99 %" in instruction
        assert "Glasgow" not in instruction
        assert "None" not in instruction


@pytest.mark.parametrize("langue", [Langue.FR, Langue.EN])
def test_toutes_les_questions_sont_bilingues(langue):
    entretien = Entretien(langue=langue)
    question = entretien.prochaine_question()
    assert question is not None
    assert question.texte(langue).strip()
