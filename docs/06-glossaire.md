# 06 — Bases théoriques et glossaire (Étape 0)

## SFT — Supervised Fine-Tuning

Méthode d'entraînement où l'on prend un **modèle déjà pré-entraîné** et où on
l'**affine avec des exemples bien annotés** (questions/réponses,
consignes/réalisations, etc.).

Le modèle apprend ainsi à **mieux suivre les attentes humaines** en copiant les
bons comportements montrés dans ces données supervisées.

## DPO — Direct Preference Optimization

Méthode d'**alignement des modèles de langage basée sur des préférences
humaines**.

L'idée est d'entraîner le modèle à générer des réponses qui correspondent
davantage aux attentes humaines **sans passer par un modèle de récompense
intermédiaire**.

En pratique, le DPO apprend **directement à partir de paires de réponses
annotées** par des humains, en indiquant laquelle est préférée.

## Autres termes du projet

| Terme | Définition |
|---|---|
| **LoRA** | *Low-Rank Adaptation* — n'entraîne que de petites matrices de rang faible injectées dans le modèle gelé. Réduit fortement la VRAM et la taille des poids à livrer. |
| **PEFT** | *Parameter-Efficient Fine-Tuning* — famille de méthodes dont LoRA fait partie ; bibliothèque Hugging Face du même nom. |
| **GRPO** | *Group Relative Policy Optimization* — alternative d'alignement citée à l'étape 2 comme option à DPO. |
| **vLLM** | Moteur d'inférence LLM haute performance (PagedAttention, batching continu), API compatible OpenAI. |
| **Presidio** | Outil open source Microsoft de détection et masquage de données sensibles (PII). |
| **POC** | *Proof of Concept* — démontre la faisabilité, n'est pas un produit de production. |
| **Sous-triage** | Classer un cas critique comme non urgent. Erreur la plus dangereuse pour ce système. |
| **Sur-triage** | Classer un cas bénin comme urgence maximale. Coûteux mais non dangereux. |
| **Sous-triage critique** | Minorer une **urgence maximale**. Métrique de sécurité de premier rang : c'est elle qui décide d'un déploiement clinique, pas l'exactitude globale. |
| **Adaptateur** | Les poids LoRA seuls, hors modèle de base. 67 Mo ici, contre 3,4 Go pour le modèle complet. |
| **`rewards/margins`** | En DPO, l'écart que le modèle creuse entre la réponse retenue et la réponse écartée. Mesure l'alignement, **pas** la qualité clinique. |
| **Ablation** | Retirer un composant pour mesurer sa contribution réelle. Ici : retirer les paires de triage du jeu DPO pour isoler la cause d'une dégradation. |
| **Motif réservé** | Motif de recours utilisé uniquement à l'évaluation. Distingue l'apprentissage d'une règle de la mémorisation d'un gabarit. |

## Sources de données citées

| Source | Langue | Nature | Statut |
|---|---|---|---|
| **MediQAl** (`ANR-MALADES/MediQAl`) | FR | QCM + questions ouvertes sur cas cliniques — CC-BY-4.0 | ✅ retenue |
| **UltraMedical-Preference** (`TsinghuaC3I/...`) | EN | Paires préférentielles médicales → base du DPO — MIT | ✅ retenue |
| MediQA | EN | Q/R médicales | ❌ indisponible |
| FrenchMedMCQA | FR | QCM médicaux | ❌ indisponible → couvert par MediQAl |
| MedQuAD | EN | Q/R médicales NIH | ❌ indisponible → couvert par UltraMedical |

Détail complet : [03b — Inventaire vérifié des sources](03b-inventaire-sources.md).

> Vérifier et documenter la **licence** de chaque source avant redistribution
> (exigence de l'étape 1).
