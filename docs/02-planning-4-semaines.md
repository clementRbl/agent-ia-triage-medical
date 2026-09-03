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

| Semaine | Focus | Sortie concrète | État |
|---|---|---|---|
| S1 | Données | 5 000 paires SFT + 3 000 paires DPO, anonymisées, splits sans fuite | ✅ |
| S2 | SFT + LoRA | adaptateur 67 Mo, 91,92 % d'exactitude, 0 urgence manquée | ✅ |
| S3 | DPO | adaptateur aligné, comparaison base/SFT/DPO, 92,93 % | ✅ |
| S4 | Déploiement | service complet, image Docker, application Modal, livraison continue, mesures | ✅ |
| S4 | Évaluation élargie | 600 cas / 200 urgences, 14 motifs réservés, intervalles de confiance | ✅ |
| S4 | Rapport | PDF ≤ 20 pages + roadmap de passage à l'échelle | ⏳ |

Résultats mesurés : [04b — Résultats d'entraînement](04b-resultats-entrainement.md).

## Écarts par rapport au planning initial

- **Sources de données** : MediQA, FrenchMedMCQA et MedQuAD n'étaient plus
  accessibles. MediQAl et UltraMedical-Preference les remplacent —
  [03b](03b-inventaire-sources.md).
- **Cas de triage** : aucun corpus disponible ne porte de niveau de priorité.
  Un bloc de cas construits par règles explicites comble ce manque —
  [03c](03c-plan-composition-dataset.md).
- **DPO** : trois runs ont été nécessaires. Les deux premiers dégradaient le
  modèle ; une ablation a isolé la cause — [04b](04b-resultats-entrainement.md).
- **CI/CD** : mise en place dès la semaine 1 plutôt qu'en semaine 4, pour
  garder toutes les livraisons suivantes.
- **Jeu d'évaluation** : élargi en semaine 4, de 120 à 600 cas. Avec
  40 urgences, l'intervalle de confiance du sous-triage critique allait de
  5,5 % à 26,1 % ; aucun seuil d'acceptation n'était fixable. La mesure élargie
  a révélé un taux réel de 8,5 % là où l'échantillon réduit en montrait 2,5 %.
- **Garde-fou de sécurité** : non prévu au cahier des charges, ajouté en
  conséquence de cette mesure. Un sous-triage critique de 8,5 % interdit de
  servir le modèle seul ; un barème explicite relève la priorité en cas de
  désaccord — [05](05-etape-3-deploiement.md).
- **Hébergement** : Modal, dont le plan gratuit fournit un vrai GPU. Les autres
  offres gratuites sont limitées au CPU, où vLLM perdrait sa raison d'être.
