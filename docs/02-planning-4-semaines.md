# 02 — Feuille de route (4 semaines)

## Semaine 1 — Préparation et structuration des données

- Agrégation des corpus médicaux francophones et anglophones :
  **MediQA**, **FrenchMedMCQA**, **MedQuAD**, **UltraMedical-Preference**.
- Constitution d'un dataset **SFT de 5 000 paires instruction-réponse**.
- Création du dataset **DPO** (paires réponses validées / non validées).
- **Anonymisation** et validation de la **conformité RGPD**.

## Semaine 2 — Fine-Tuning Supervisé (SFT)

Objectif : spécialiser le modèle de base sur le corpus médical.

- Implémentation du SFT sur **Qwen3-1.7B-Base**.
- Optimisation **LoRA** (Low-Rank Adaptation) pour économiser la VRAM.
- **Validation intermédiaire** sur un jeu de test : mesurer les progrès et
  vérifier que l'entraînement se déroule correctement.

## Semaine 3 — Alignement par préférences (DPO)

Objectif : affiner le comportement du modèle sur les attentes cliniques.

- Entraînement **DPO** du modèle déjà fine-tuné, sur les paires préférentielles
  d'**UltraMedical-Preference**.
- **Alignement clinique** : apprendre à distinguer les réponses de meilleure
  qualité des réponses moins pertinentes ou incorrectes.

## Semaine 4 — Déploiement et validation

**Mise en production pilote**
- Déploiement d'un endpoint prototype via **vLLM**.
- Simulation d'inférence en conditions quasi-réelles.
- Tests de **latence**, **pertinence**, **traçabilité** des interactions.

**Évaluation finale**
- Analyse des métriques de performance.
- Rédaction du rapport de synthèse.
- Recommandations stratégiques pour le passage à l'échelle.

## Vue synthétique

| Semaine | Focus | Sortie concrète |
|---|---|---|
| S1 | Données | `data/` SFT 5k + DPO, anonymisés, splits train/val/test |
| S2 | SFT + LoRA | adaptateur SFT + métriques intermédiaires |
| S3 | DPO | adaptateur aligné + comparaison base/SFT/DPO |
| S4 | Déploiement | endpoint vLLM + CI/CD + rapport PDF |
