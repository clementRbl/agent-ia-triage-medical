"""Alignement par preferences (DPO) a partir du modele issu du SFT.

Le modele de reference exige par le DPO n'est pas charge une seconde fois :
avec PEFT, desactiver l'adaptateur redonne le modele de depart. On economise
ainsi ~3,4 Go de VRAM, ce qui est determinant sur une carte de 10 Go.
"""

from __future__ import annotations

import os

# Les sequences du jeu de preferences ont des longueurs tres variables, ce qui
# fragmente le tas CUDA : l'entrainement echoue avec plus d'un gigaoctet
# reserve mais inutilisable. Les segments extensibles reutilisent ces blocs.
# A definir avant toute initialisation du contexte CUDA, donc des l'import.
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

import json
from math import ceil
from pathlib import Path
from typing import Any

import mlflow
import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer
from trl import DPOConfig, DPOTrainer

from triage.audit import Manifeste
from triage.training.config import ConfigDPO
from triage.training.donnees import charger_dpo
from triage.training.sft import SUIVI_MLFLOW


def _config_entrainement(config: ConfigDPO, nb_exemples: int, pas_max: int | None) -> DPOConfig:
    par_epoch = max(1, ceil(nb_exemples / config.lot_effectif))
    pas_totaux = pas_max or max(1, int(par_epoch * config.epochs))
    return DPOConfig(
        output_dir=str(config.sortie),
        num_train_epochs=config.epochs,
        max_steps=pas_max or -1,
        per_device_train_batch_size=config.taille_lot,
        per_device_eval_batch_size=config.taille_lot_eval,
        eval_accumulation_steps=config.accumulation_evaluation,
        gradient_accumulation_steps=config.accumulation,
        learning_rate=config.taux_apprentissage,
        lr_scheduler_type=config.planificateur,
        warmup_steps=int(pas_totaux * config.part_echauffement),
        weight_decay=config.decroissance_poids,
        beta=config.beta,
        max_length=config.longueur_max,
        bf16=config.bf16,
        gradient_checkpointing=config.checkpoint_gradient,
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
        run_name=config.nom_run or "dpo",
        optim="adamw_torch",
    )


def entrainer_dpo(
    config: ConfigDPO | None = None,
    limite_train: int | None = None,
    limite_eval: int | None = None,
    pas_max: int | None = None,
) -> dict[str, Any]:
    """Aligne le modele deja specialise sur les paires de preferences."""
    config = config or ConfigDPO()
    if not config.adaptateur_sft.exists():
        raise FileNotFoundError(
            f"Adaptateur SFT introuvable : {config.adaptateur_sft}. "
            "Lancez d'abord l'entraînement supervisé."
        )
    config.sortie.mkdir(parents=True, exist_ok=True)

    tokenizer = AutoTokenizer.from_pretrained(str(config.adaptateur_sft))
    if tokenizer is None:
        raise RuntimeError("Tokenizer introuvable dans l'adaptateur SFT")

    base = AutoModelForCausalLM.from_pretrained(
        config.modele,
        dtype=torch.bfloat16 if config.bf16 else torch.float32,
        device_map={"": 0} if torch.cuda.is_available() else None,
    )
    # `is_trainable` : on poursuit l'entrainement de l'adaptateur du SFT plutot
    # que d'en repartir un neuf, sinon l'alignement effacerait la
    # specialisation medicale acquise.
    modele = PeftModel.from_pretrained(base, str(config.adaptateur_sft), is_trainable=True)
    modele.config.use_cache = False

    entrainement = charger_dpo("train", limite=limite_train)
    validation = charger_dpo("validation", limite=limite_eval)

    trainer = DPOTrainer(
        model=modele,
        ref_model=None,  # l'adaptateur desactive tient lieu de reference
        args=_config_entrainement(config, len(entrainement), pas_max),
        train_dataset=entrainement,
        eval_dataset=validation,
        processing_class=tokenizer,
    )

    mlflow.set_tracking_uri(SUIVI_MLFLOW)
    mlflow.set_experiment(config.experience_mlflow)

    with mlflow.start_run(run_name=config.nom_run or None):
        mlflow.log_params(config.en_dict())
        mlflow.log_params(
            {"exemples_train": len(entrainement), "exemples_validation": len(validation)}
        )

        resultat = trainer.train()
        evaluation = trainer.evaluate()

        adaptateur = config.sortie / "adaptateur"
        trainer.save_model(str(adaptateur))
        mlflow.log_artifacts(str(adaptateur), artifact_path="adaptateur")

        if torch.cuda.is_available():
            mlflow.log_metric("vram_max_go", round(torch.cuda.max_memory_allocated() / 1e9, 2))

        metriques = {
            **{f"train_{k}": v for k, v in resultat.metrics.items()},
            **evaluation,
        }
        (config.sortie / "metriques.json").write_text(
            json.dumps(metriques, indent=2), encoding="utf-8"
        )

    manifeste = Manifeste(
        etape="entrainement_dpo",
        parametres=config.en_dict() | {"adaptateur_sft": str(config.adaptateur_sft)},
        statistiques=metriques,
    )
    manifeste.ajouter_fichier(Path("data/processed/dpo.parquet"), entree=True)
    manifeste.ajouter_fichier(adaptateur / "adapter_model.safetensors", entree=False)
    manifeste.ecrire()
    return metriques
