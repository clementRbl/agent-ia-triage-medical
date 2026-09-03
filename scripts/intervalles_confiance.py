"""Intervalles de confiance et test apparie sur le jeu de generalisation.

Recalcule les taux a partir des reponses brutes, de facon reproductible pour
le rapport final : un chiffre sans intervalle ne permet pas de fixer un seuil
d'acceptation.

Usage :
    uv run python scripts/intervalles_confiance.py
    uv run python scripts/intervalles_confiance.py --suffixe _generalisation
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from triage.schema import NiveauPriorite
from triage.training.evaluation import extraire_niveau
from triage.training.inference import CAS_GENERALISATION
from triage.training.statistiques import p_valeur_appariee, wilson


def attendus_generalisation(nombre: int) -> list[NiveauPriorite]:
    """Rejoue le tirage deterministe du jeu de generalisation."""
    from triage.data.triage import PRESENTATIONS_INEDITES, generer_cas

    cas = generer_cas(
        nombre,
        graine=777,
        presentations=PRESENTATIONS_INEDITES,
        prefixe="generalisation",
    )
    return [c.niveau_priorite for c in cas if c.niveau_priorite is not None]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suffixe", default="_generalisation_dpo_ablation")
    parser.add_argument("--nombre", type=int, default=CAS_GENERALISATION)
    args = parser.parse_args()

    chemin = Path(f"outputs/reponses_evaluation{args.suffixe}.json")
    reponses_par_modele: dict[str, list[str]] = json.loads(chemin.read_text(encoding="utf-8"))
    attendus = attendus_generalisation(args.nombre)

    predits_par_modele: dict[str, list[NiveauPriorite | None]] = {}
    for nom, reponses in reponses_par_modele.items():
        if len(reponses) != len(attendus):
            raise SystemExit(
                f"[{nom}] {len(reponses)} réponses pour {len(attendus)} cas attendus : "
                "le rapport ne correspond pas au jeu régénéré."
            )
        predits_par_modele[nom] = [extraire_niveau(r) for r in reponses]

    urgences = [i for i, a in enumerate(attendus) if a is NiveauPriorite.MAXIMALE]
    print(f"jeu : {len(attendus)} cas, dont {len(urgences)} urgences maximales\n")

    for nom, predits in predits_par_modele.items():
        exacts = sum(1 for a, p in zip(attendus, predits, strict=True) if a is p)
        # Sous-triage critique : une urgence maximale annoncée à un niveau moindre.
        manquees = sum(1 for i in urgences if predits[i] is not NiveauPriorite.MAXIMALE)
        print(f"[{nom}]")
        print(f"  exactitude               {wilson(exacts, len(attendus))}")
        print(f"  sous-triage critique     {wilson(manquees, len(urgences))}\n")

    noms = list(predits_par_modele)
    for indice, premier in enumerate(noms):
        for second in noms[indice + 1 :]:
            pa, pb = predits_par_modele[premier], predits_par_modele[second]
            couples = list(zip(attendus, pa, pb, strict=True))
            a_seul = sum(1 for att, x, y in couples if x is att and y is not att)
            b_seul = sum(1 for att, x, y in couples if y is att and x is not att)
            p = p_valeur_appariee(a_seul, b_seul)
            verdict = "écart significatif" if p < 0.05 else "écart non significatif"
            print(f"[{premier}] vs [{second}] — exactitude")
            print(f"  {a_seul} cas gagnés par {premier}, {b_seul} par {second}")
            print(f"  p = {p:.3f} → {verdict}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
