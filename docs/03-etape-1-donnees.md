# 03 — Étape 1 : Collecter et structurer les données

## Objectifs

- Collecter, nettoyer et structurer un **corpus médical bilingue FR/EN** destiné
  au fine-tuning et à l'alignement par préférences.
- Produire **~5 000 paires instruction-réponse** pour le SFT.
- Constituer un jeu de **paires préférentielles (DPO)** validées cliniquement.
- **Anonymiser** toutes les données et **documenter le processus RGPD**.
- Définir le **schéma des métadonnées** : symptômes, antécédents, constantes,
  source, niveau de confiance.
- Préparer les splits **train / val / test** + des jeux d'**évaluation clinique
  séparés**.

## Prérequis

- Inventaire des sources disponibles (MediQA, FrenchMedMCQA, MedQuAD,
  UltraMedical-Preference, …).
- Accès stockage et compute (espace disque, notebooks).

## Résultats attendus

1. Dataset médical bilingue **anonymisé et versionné**, prêt pour SFT (≈5 000
   paires) et pour la constitution du jeu DPO.
2. **Schéma des métadonnées** documenté.
3. **Justification du processus RGPD** suivi.

## Anonymisation — Presidio (recommandation client)

```bash
pip install presidio-analyzer presidio-anonymizer
```

- Créer un **`AnalyzerEngine`** pour identifier les entités sensibles — a minima
  **nom et prénom des patients**.
- Créer un **`AnonymizerEngine`** pour les masquer.
- Utiliser un **modèle linguistique adapté** (ex. `fr_core_news_md`).
- Tester différentes stratégies de masquage : **`replace`**, **`mask`**,
  **`redact`**, selon les besoins.
- **Contrôler la qualité du masquage** : vérifier qu'aucune donnée personnelle
  identifiable ne subsiste.

## Recommandations

- Prioriser la **qualité** (annotations validées) sur la quantité.
- Standardiser les formats : **JSONL / HF datasets**, enregistrer les métadonnées.
- Documenter dans le repo **l'origine et la licence de chaque source**, ou
  déposer le jeu de données sur <https://huggingface.co/datasets>.

## Points de vigilance

- ❗ Ne **pas mélanger** données d'entraînement et données d'évaluation.
- ❗ Conserver une **trace de chaque transformation** de données (auditabilité).

## Outils

Hugging Face Datasets · Presidio

## Schéma de métadonnées — proposition de départ

Champs à trancher lors de la conception, à aligner sur l'énoncé :

| Champ | Type | Description |
|---|---|---|
| `id` | str | Identifiant unique stable |
| `lang` | `fr` \| `en` | Langue de la paire |
| `instruction` | str | Question / cas patient |
| `response` | str | Réponse de référence |
| `symptomes` | list[str] | Symptomatologie extraite |
| `antecedents` | list[str] | Antécédents médicaux |
| `constantes` | dict | Constantes vitales (FC, TA, SpO2, T°…) |
| `niveau_priorite` | `max` \| `moderee` \| `differee` | Cible de triage |
| `source` | str | Corpus d'origine |
| `licence` | str | Licence de la source |
| `niveau_confiance` | float \| enum | Confiance sur l'annotation |
| `anonymise` | bool | Passage Presidio effectué |
| `split` | `train` \| `val` \| `test` \| `eval_clinique` | Affectation |
