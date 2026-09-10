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
    Question,
    TypeReponse,
    question_signes,
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


class TestReconnaissanceDuMotif:
    """Le motif saisi choisit les signes de gravite depistes.

    Un patient ne se presente pas avec le terme du bareme : il dit « toux »,
    pas « dyspnee ». Tomber dans le repli general lui fait chercher des
    troubles de la vigilance au lieu d'une cyanose.
    """

    @pytest.mark.parametrize("motif", ["toux", "toux grasse depuis trois jours", "essoufflement"])
    def test_un_symptome_de_dyspnee_ramene_les_signes_respiratoires(self, motif):
        signes = signes_a_rechercher(motif, Langue.FR)
        assert "cyanose" in signes
        assert signes != SIGNES_GENERAUX["fr"]

    def test_le_motif_du_bareme_reste_prioritaire(self):
        """La premiere passe porte sur les motifs : elle ne doit pas etre court-circuitee."""
        signes = signes_a_rechercher("douleur thoracique oppressive", Langue.FR)
        assert "irradiation au bras gauche" in signes

    def test_un_motif_inconnu_retombe_sur_les_signes_generaux(self):
        assert signes_a_rechercher("consultation de contrôle", Langue.FR) == SIGNES_GENERAUX["fr"]


class TestAideALaSaisie:
    """L'aide affichee avec chaque constante.

    Une constante mal comprise est saisie de travers, et une saisie de travers
    produit un triage faux sans declencher la moindre erreur : la borne accepte
    la valeur, le bareme la lit telle quelle. L'aide est un dispositif de
    securite, pas un confort.
    """

    def test_chaque_constante_porte_une_aide_dans_les_deux_langues(self):
        for question in QUESTIONS_CONSTANTES:
            for langue in (Langue.FR, Langue.EN):
                aide = question.texte_aide(langue)
                assert aide, f"{question.cle} n'a pas d'aide en {langue.value}"

    def test_l_aide_du_glasgow_donne_les_trois_composantes(self):
        """C'est le seul item qui se calcule : le detail doit etre servi avec."""
        aide = QUESTIONS_CONSTANTES[0].texte_aide(Langue.FR)
        assert QUESTIONS_CONSTANTES[0].cle == "glasgow"
        assert aide is not None
        for composante in ("ouverture des yeux", "réponse verbale", "réponse motrice"):
            assert composante in aide.casefold()

    def test_l_aide_du_glasgow_situe_le_seuil_du_bareme(self):
        """« Pourquoi 14 ne declenche rien » est la question qui revient."""
        aide = QUESTIONS_CONSTANTES[0].texte_aide(Langue.FR)
        assert aide is not None and "14" in aide

    def test_l_aide_de_la_frequence_respiratoire_ecarte_la_confusion_avec_le_pouls(self):
        """60 saisi ici decrit une detresse majeure, pas un coeur normal."""
        question = next(q for q in QUESTIONS_CONSTANTES if q.cle == "frequence_respiratoire")
        aide = question.texte_aide(Langue.FR)
        assert aide is not None and "pouls" in aide.casefold()

    def test_l_aide_de_la_saturation_enonce_la_limite_du_bareme(self):
        """Le sur-triage de l'insuffisant respiratoire chronique est assume, donc dit."""
        question = next(q for q in QUESTIONS_CONSTANTES if q.cle == "saturation")
        aide = question.texte_aide(Langue.FR)
        assert aide is not None and "insuffisant respiratoire chronique" in aide

    def test_la_question_des_signes_explique_qu_elle_conclut(self):
        """Repondre « oui » arrete le recueil : le dire evite un oui de politesse."""
        aide = question_signes("douleur thoracique", Langue.FR).texte_aide(Langue.FR)
        assert aide is not None
        assert "urgence maximale" in aide
        assert "dépendent du motif" in aide

    def test_une_question_sans_aide_ne_ment_pas(self):
        """Le champ vaut None plutot qu'une chaine vide : le client sait quoi masquer."""
        assert (
            Question(
                cle="essai", libelle={"fr": "?", "en": "?"}, type_reponse=TypeReponse.TEXTE
            ).texte_aide(Langue.FR)
            is None
        )


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
