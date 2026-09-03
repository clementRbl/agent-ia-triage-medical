"""Publie l'adaptateur LoRA et sa carte de modele sur le Hub Hugging Face.

Le livrable demande « les poids finaux du modele ». Ce sont ceux de
l'adaptateur, pas ceux du modele complet : LoRA n'entraine que 0,8 % des
parametres, et les 1,7 milliard restants sont ceux, publics, de Qwen3-1.7B.
Republier le modele fusionne ferait 3,4 Go pour redistribuer a l'identique
des poids deja disponibles ; l'adaptateur en fait 67 et se recompose en une
ligne. C'est aussi ce que vLLM sait charger directement.

Prerequis : un jeton d'ecriture Hugging Face dans HF_TOKEN.

Usage :
    uv run python scripts/publier_modele.py --depot <compte>/triage-chsa-qwen3-1.7b
    uv run python scripts/publier_modele.py --depot ... --prive --essai
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Final

# Ce que l'entrainement laisse dans le dossier mais qui n'a rien a faire dans
# un modele publie :
#   ref/            l'adaptateur de reference du DPO, copie du SFT. Il double
#                   la taille du depot et PEFT le chargerait comme un
#                   sous-modele s'il le trouvait.
#   training_args.* un pickle des arguments d'entrainement. Inutile a
#                   l'inference, et telecharger un pickle depuis un depot
#                   public revient a executer du code qu'on n'a pas lu.
# `delete_patterns` les retire aussi d'une publication anterieure.
EXCLUS: Final[tuple[str, ...]] = ("ref/*", "training_args.bin", "optimizer.pt")

CARTE = """---
license: apache-2.0
base_model: Qwen/Qwen3-1.7B-Base
library_name: peft
tags:
  - triage
  - medical
  - lora
language:
  - fr
  - en
---

# Agent d'aide au triage aux urgences — adaptateur LoRA

Adaptateur LoRA de `Qwen/Qwen3-1.7B-Base`, entraîné par fine-tuning supervisé
puis aligné par préférences, pour évaluer un niveau de priorité de triage à
partir d'un tableau clinique en français ou en anglais.

## Limites d'usage

**Preuve de concept, non certifiée dispositif médical.** Ce modèle ne pose pas
de diagnostic, ne prescrit pas, et ne remplace aucune décision soignante. Le
barème employé est une transposition simplifiée de l'échelle FRENCH à trois
niveaux, **non validée par un clinicien**. Le périmètre est l'adulte : la
pédiatrie et l'obstétrique en sont exclues.

Le modèle **ne doit pas être servi seul**. Le service de référence le double
d'un barème explicite qui relève la priorité lorsque le modèle annonce moins
grave que les constantes ne le justifient.

## Format d'entrée

Le modèle attend le format exact vu à l'entraînement. Toute autre mise en
forme dégrade les performances sans signal visible.

```
Patient de 68 ans, sexe masculin.
Motif de recours : douleur thoracique.
Symptômes rapportés : irradiation au bras gauche, pâleur.
Antécédents : hypertension artérielle, tabagisme.
Constantes à l'admission : FC 118/min, PA 88/55 mmHg, FR 32/min, SpO2 88 %, T 37,4 °C, Glasgow 14, EVA 8/10.

Évaluez le niveau de priorité de triage et justifiez votre évaluation.
```

Le gabarit de conversation est appliqué avec `enable_thinking=False`.

## Performances mesurées

{performances}

Le **sous-triage critique** — une urgence maximale annoncée à un niveau
moindre — est la métrique de sécurité du projet. Un sur-triage encombre le
service ; un sous-triage laisse un patient grave en salle d'attente. Les deux
ne se compensent pas et ne sont jamais agrégés.

Mesures obtenues sur {total} cas construits à partir de motifs de recours
**jamais vus à l'entraînement**, intervalles de Wilson à 95 %.

## Chargement

```python
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

base = AutoModelForCausalLM.from_pretrained("Qwen/Qwen3-1.7B-Base")
modele = PeftModel.from_pretrained(base, "{depot}")
tokenizer = AutoTokenizer.from_pretrained("{depot}")
```

Avec vLLM :

```bash
vllm serve Qwen/Qwen3-1.7B-Base \\
  --enable-lora --max-lora-rank 16 \\
  --lora-modules triage={depot}
```
"""


def _tableau_performances(rapport: Path) -> tuple[str, int]:
    """Met en forme les mesures du rapport d'evaluation."""
    from triage.training.statistiques import wilson

    if not rapport.exists():
        return "_Mesures non disponibles._", 0

    resultats = json.loads(rapport.read_text(encoding="utf-8"))
    lignes = [
        "| Modèle | Exactitude | Sous-triage critique |",
        "| --- | --- | --- |",
    ]
    total = 0
    for resultat in resultats:
        total = resultat["total"]
        urgences = sum(resultat["matrice"]["maximale"].values())
        exactitude = wilson(resultat["exacts"], total)
        critique = wilson(resultat["sous_triages_critiques"], urgences)
        lignes.append(
            f"| `{resultat['nom']}` | {100 * exactitude.proportion:.1f} % "
            f"[{100 * exactitude.borne_basse:.1f} à {100 * exactitude.borne_haute:.1f}] "
            f"| {100 * critique.proportion:.1f} % "
            f"[{100 * critique.borne_basse:.1f} à {100 * critique.borne_haute:.1f}] |"
        )
    return "\n".join(lignes), total


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--depot", required=True, help="identifiant <compte>/<nom> sur le Hub")
    parser.add_argument(
        "--adaptateur",
        type=Path,
        default=Path("outputs/dpo_ablation/adaptateur"),
        help="dossier de l'adaptateur à publier",
    )
    parser.add_argument(
        "--rapport",
        type=Path,
        default=Path("outputs/evaluation_generalisation_dpo_ablation.json"),
    )
    parser.add_argument("--prive", action="store_true", help="créer un dépôt privé")
    parser.add_argument("--essai", action="store_true", help="tout préparer sans rien envoyer")
    args = parser.parse_args()

    if not args.adaptateur.exists():
        raise SystemExit(f"Adaptateur introuvable : {args.adaptateur}")

    performances, total = _tableau_performances(args.rapport)
    carte = CARTE.format(depot=args.depot, performances=performances, total=total)
    chemin_carte = args.adaptateur / "README.md"
    chemin_carte.write_text(carte, encoding="utf-8")
    print(f"carte de modèle écrite : {chemin_carte}")

    if args.essai:
        print("\n--- essai : rien n'a été envoyé ---")
        print(carte)
        return 0

    if not os.environ.get("HF_TOKEN"):
        raise SystemExit(
            "HF_TOKEN absent. Créez un jeton d'écriture sur "
            "https://huggingface.co/settings/tokens puis exportez-le."
        )

    from huggingface_hub import HfApi

    api = HfApi()
    api.create_repo(args.depot, repo_type="model", private=args.prive, exist_ok=True)
    api.upload_folder(
        folder_path=str(args.adaptateur),
        repo_id=args.depot,
        repo_type="model",
        ignore_patterns=list(EXCLUS),
        delete_patterns=list(EXCLUS),
        commit_message="Adaptateur LoRA de triage, aligné par préférences",
    )
    print(f"publié : https://huggingface.co/{args.depot}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
