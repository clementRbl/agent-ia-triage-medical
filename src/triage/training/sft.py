"""Fine-tuning supervise de Qwen3-1.7B-Base par LoRA.

Contrainte materielle : 10 Go de VRAM. D'ou l'assemblage retenu -- poids en
bf16, adaptateurs LoRA plutot qu'un entrainement complet, lots de 2 exemples
compenses par accumulation, et checkpoint de gradient.
"""

from __future__ import annotations

import json
from math import ceil
from pathlib import Path
from typing import Any

import mlflow
import torch
from peft import LoraConfig
from transformers import AutoModelForCausalLM, AutoTokenizer
from trl import SFTConfig, SFTTrainer

from triage.audit import Manifeste
from triage.training.config import ConfigSFT
from triage.training.donnees import charger_sft

# MLflow 3 a mis le stockage fichier en maintenance : le backend recommande
# en local est SQLite. La base et les artefacts restent sur la machine.
SUIVI_MLFLOW = "sqlite:///mlflow.db"


def _config_lora(config: ConfigSFT) -> LoraConfig:
    return LoraConfig(
        r=config.rang,
        lora_alpha=config.alpha,
        lora_dropout=config.dropout,
        target_modules=list(config.modules_cibles),
        bias="none",
        task_type="CAUSAL_LM",
    )


def _pas_totaux(config: ConfigSFT, nb_exemples: int, pas_max: int | None) -> int:
    if pas_max:
        return pas_max
    par_epoch = max(1, ceil(nb_exemples / config.lot_effectif))
    return max(1, int(par_epoch * config.epochs))


def _config_entrainement(config: ConfigSFT, nb_exemples: int, pas_max: int | None) -> SFTConfig:
    # Cette version de TRL n'expose que `warmup_steps` : on convertit la part
    # voulue en nombre de pas a partir du volume reel du jeu.
    pas_echauffement = int(_pas_totaux(config, nb_exemples, pas_max) * config.part_echauffement)
    return SFTConfig(
        output_dir=str(config.sortie),
        num_train_epochs=config.epochs,
        max_steps=pas_max or -1,
        per_device_train_batch_size=config.taille_lot,
        per_device_eval_batch_size=config.taille_lot_eval,
        gradient_accumulation_steps=config.accumulation,
        learning_rate=config.taux_apprentissage,
        lr_scheduler_type=config.planificateur,
        warmup_steps=pas_echauffement,
        weight_decay=config.decroissance_poids,
        max_length=config.longueur_max,
        bf16=config.bf16,
        gradient_checkpointing=config.checkpoint_gradient,
        # LoRA + checkpoint de gradient : la variante non reentrante est la
        # seule qui propage correctement les gradients aux adaptateurs.
        gradient_checkpointing_kwargs={"use_reentrant": False},
        logging_steps=config.pas_journalisation,
        eval_strategy="steps",
        eval_steps=config.pas_evaluation,
        save_strategy="steps",
        save_steps=config.pas_evaluation,
        save_total_limit=config.checkpoints_conserves,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        seed=config.graine,
        data_seed=config.graine,
        report_to=["mlflow"],
        run_name=config.nom_run or "sft",
        # Le jeu est deja melange et decoupe par groupe : pas de regroupement
        # d'exemples, qui melangerait des cas cliniques distincts.
        packing=False,
        optim="adamw_torch",
    )


def _resume_parametres(modele: Any) -> dict[str, int | float]:
    entrainables = sum(p.numel() for p in modele.parameters() if p.requires_grad)
    total = sum(p.numel() for p in modele.parameters())
    return {
        "parametres_total": total,
        "parametres_entrainables": entrainables,
        "part_entrainable_pct": round(100 * entrainables / total, 4),
    }


def entrainer_sft(
    config: ConfigSFT | None = None,
    limite_train: int | None = None,
    limite_eval: int | None = None,
    pas_max: int | None = None,
) -> dict[str, Any]:
    """Lance un run de SFT et retourne ses metriques.

    Les arguments `limite_*` et `pas_max` servent aux verifications rapides de
    la chaine avant un entrainement complet.
    """
    config = config or ConfigSFT()
    config.sortie.mkdir(parents=True, exist_ok=True)

    tokenizer = AutoTokenizer.from_pretrained(config.modele)
    modele = AutoModelForCausalLM.from_pretrained(
        config.modele,
        dtype=torch.bfloat16 if config.bf16 else torch.float32,
        device_map={"": 0} if torch.cuda.is_available() else None,
    )
    modele.config.use_cache = False  # incompatible avec le checkpoint de gradient

    entrainement = charger_sft("train", dossier=config.dossier_donnees, limite=limite_train)
    validation = charger_sft("validation", dossier=config.dossier_donnees, limite=limite_eval)

    trainer = SFTTrainer(
        model=modele,
        args=_config_entrainement(config, len(entrainement), pas_max),
        train_dataset=entrainement,
        eval_dataset=validation,
        processing_class=tokenizer,
        peft_config=_config_lora(config),
    )

    mlflow.set_tracking_uri(SUIVI_MLFLOW)
    mlflow.set_experiment(config.experience_mlflow)

    with mlflow.start_run(run_name=config.nom_run or None):
        mlflow.log_params(config.en_dict())
        mlflow.log_params(_resume_parametres(trainer.model))
        mlflow.log_params(
            {"exemples_train": len(entrainement), "exemples_validation": len(validation)}
        )

        resultat = trainer.train()
        evaluation = trainer.evaluate()

        if torch.cuda.is_available():
            mlflow.log_metric("vram_max_go", round(torch.cuda.max_memory_allocated() / 1e9, 2))

        # `save_model` ecrit l'adaptateur LoRA et le tokenizer : passer par le
        # trainer evite de manipuler directement le modele enveloppe par PEFT.
        adaptateur = config.sortie / "adaptateur"
        trainer.save_model(str(adaptateur))
        mlflow.log_artifacts(str(adaptateur), artifact_path="adaptateur")

        metriques = {
            **{f"train_{k}": v for k, v in resultat.metrics.items()},
            **evaluation,
        }
        (config.sortie / "metriques.json").write_text(
            json.dumps(metriques, indent=2), encoding="utf-8"
        )

    manifeste = Manifeste(
        etape="entrainement_sft",
        parametres=config.en_dict(),
        statistiques={
            **metriques,
            **_resume_parametres(trainer.model),
            "vram_max_go": round(torch.cuda.max_memory_allocated() / 1e9, 2)
            if torch.cuda.is_available()
            else None,
        },
    )
    manifeste.ajouter_fichier(Path("data/processed/sft.parquet"), entree=True)
    manifeste.ajouter_fichier(adaptateur / "adapter_model.safetensors", entree=False)
    manifeste.ecrire()
    return metriques
