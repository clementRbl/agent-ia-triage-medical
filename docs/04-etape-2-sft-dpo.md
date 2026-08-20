# 04 — Étape 2 : Affiner et aligner le modèle

## Objectifs

- **SFT** de `Qwen3-1.7B-Base` avec **LoRA** pour limiter l'empreinte GPU.
- Puis **alignement par préférences (DPO / GRPO)** sur les paires préférentielles.
- **Valider** les performances intermédiaires sur les jeux de test cliniques.
- Réaliser les **contrôles de sécurité** : hallucinations, recommandations
  dangereuses.
- **Itérer** sur hyperparamètres et checkpoints en gardant la traçabilité :
  fichiers de logs, métriques, checkpoints pour reprise d'entraînement.

## Prérequis

- Accès GPU et environnement ML (PyTorch / HF Transformers / Unsloth).
- **Métriques d'évaluation cliniques et seuils d'acceptation définis.**
- Sauvegarde/monitoring des modèles et des logs d'entraînement en place.

## Résultat attendu

Modèle Qwen3-1.7B adapté (**SFT LoRA + DPO**) avec métriques d'évaluation
documentées et **checkpoints reproductibles**.

## Recommandations

- Commencer par de **petits runs LoRA** pour valider la pipeline avant montée
  en charge.
- Mettre en place des **checkpoints**.
- Enregistrer et documenter **chaque version : hyperparamètres + seed**.

## Points de vigilance

- ❗ Éviter le **sur-apprentissage** sur les exemples annotés.

## Outils

PyTorch · Hugging Face Transformers · **PEFT (LoRA)** · **MLflow** ou
**Weights & Biases** pour le tracking.

## Contrainte matérielle locale

GPU disponible : **RTX 3080, 10 Go VRAM**.

Implications à valider en début de S2 :
- Qwen3-1.7B en bf16 ≈ 3,4 Go de poids → LoRA tient en 10 Go.
- Longueur de séquence et batch size à calibrer (gradient accumulation,
  gradient checkpointing si besoin).
- DPO : le modèle de référence peut être obtenu en désactivant l'adaptateur
  LoRA plutôt qu'en chargeant un second modèle → économie de VRAM.

## Métriques à définir avant de lancer (seuils go/no-go)

- **Pertinence clinique** : exactitude du niveau de priorité prédit
  (accuracy, matrice de confusion sur 3 classes).
- **Sécurité** : taux de sous-triage (classer « différé » un cas critique) —
  métrique la plus critique, à pondérer fortement.
- **Hallucinations** : taux de réponses contenant des affirmations non étayées.
- **Qualité de génération** : évaluation humaine ou LLM-as-judge sur un
  échantillon.
- **Latence** (mesurée à l'étape 3).
