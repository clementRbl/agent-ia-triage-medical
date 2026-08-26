"""Compare les etats successifs du modele sur les memes cas de triage.

Usage :
    uv run python scripts/evaluer_triage.py                 # base + SFT
    uv run python scripts/evaluer_triage.py --dpo           # ajoute le DPO
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from triage.training.inference import (
    ecrire_rapport,
    evaluer_generalisation,
    evaluer_modele,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dpo", action="store_true", help="évaluer aussi l'adaptateur DPO")
    parser.add_argument("--limite", type=int, default=None, help="nombre de cas")
    parser.add_argument("--split", default="test")
    parser.add_argument(
        "--generalisation",
        action="store_true",
        help="évaluer sur des motifs de recours jamais vus à l'entraînement",
    )
    args = parser.parse_args()

    a_evaluer: list[tuple[str, Path | None]] = [
        ("base", None),
        ("sft", Path("outputs/sft/adaptateur")),
    ]
    if args.dpo:
        a_evaluer.append(("dpo", Path("outputs/dpo/adaptateur")))

    resultats = []
    reponses_par_modele = {}
    for nom, adaptateur in a_evaluer:
        if adaptateur is not None and not adaptateur.exists():
            print(f"[{nom}] adaptateur absent, ignoré")
            continue
        print(f"[{nom}] génération en cours…", flush=True)
        if args.generalisation:
            resultat, reponses = evaluer_generalisation(
                f"{nom}_generalisation", adaptateur=adaptateur, nombre=args.limite or 120
            )
        else:
            resultat, reponses = evaluer_modele(
                nom, adaptateur=adaptateur, split=args.split, limite=args.limite
            )
        resultats.append(resultat)
        reponses_par_modele[nom] = reponses

        print(f"  exactitude       {100 * resultat.exactitude:6.2f} %")
        print(
            f"  sous-triage      {100 * resultat.taux_sous_triage:6.2f} %  ← métrique de sécurité"
        )
        print(f"  sur-triage       {100 * resultat.taux_sur_triage:6.2f} %")
        print(f"  sans niveau      {100 * resultat.taux_sans_niveau:6.2f} %", flush=True)

    suffixe = "_generalisation" if args.generalisation else ""
    chemin = ecrire_rapport(resultats, Path(f"outputs/evaluation{suffixe}.json"))
    Path(f"outputs/reponses_evaluation{suffixe}.json").write_text(
        json.dumps(reponses_par_modele, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nrapport écrit : {chemin}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
