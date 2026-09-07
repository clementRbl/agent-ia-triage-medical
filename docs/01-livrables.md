# 01 — Livrables attendus

## Les 5 livrables

### L1 — Dataset médical bilingue prêt à l'emploi
Corpus médical FR + EN nettoyé, structuré, **anonymisé (RGPD)**.
Format **JSONL / Hugging Face Datasets**, versionné sur un dépôt.
Optimisé pour les deux phases : SFT (~5 000 paires) et DPO (paires
préférentielles chosen/rejected).

### L2 — Modèle d'IA spécialisé et optimisé
Qwen3-1.7B fine-tuné **SFT + LoRA**, puis aligné **DPO**.
**Les poids finaux sont fournis** (adaptateurs LoRA + éventuel modèle mergé).

### L3 — Endpoint de démonstration déployé sur le cloud
API fonctionnelle et accessible, servie par **vLLM** pour une inférence rapide.
Fournisseur cloud libre. Conteneurisation **Docker**, exposition **FastAPI**.

### L4 — Pipeline CI/CD **GitHub Actions**
Automatisation des tests et du déploiement des nouvelles versions du modèle.
Objectif : maintenabilité et évolutivité.

### L5 — Rapport technique + recommandations stratégiques
**PDF, 20 pages maximum**, contenant :
- la méthodologie de préparation des données et d'entraînement ;
- les métriques de performance (latence, pertinence, etc.) ;
- l'analyse des résultats obtenus ;
- une **roadmap de passage à l'échelle** au sein du CHSA.

## Rattachement livrable ↔ activité

| Activité | Livrable |
|---|---|
| Préparation et structuration des données | L1 — Dataset bilingue (HF Datasets / JSONL, versionné) |
| Entraînement SFT + LoRA | L2 — Modèle spécialisé |
| Alignement DPO | L2 — Modèle aligné |
| Déploiement et validation | L3 endpoint vLLM cloud + L4 CI/CD GitHub Actions + L5 rapport PDF |

## Convention de dépôt sur la plateforme

Archive **zip** nommée : `Titre_du_projet_nom_prenom`

Fichiers à l'intérieur : `Nom_Prenom_<n° du livrable>_<nom du livrable>_<mmaaaa date de démarrage>`

Exemple fourni : `Janek_Meriem_1_X_012025`

**Pour ce projet** (démarrage août 2026 → `082026`) :

| N° | Nom de fichier |
|---|---|
| 1 | `Reboul_Clement_1_Dataset_082026` |
| 2 | `Reboul_Clement_2_Modele_082026` |
| 3 | `Reboul_Clement_3_Endpoint_082026` |
| 4 | `Reboul_Clement_4_CICD_082026` |
| 5 | `Reboul_Clement_5_Rapport_082026` |

Archive : `Agent_IA_Triage_Medical_Reboul_Clement.zip`

> ⚠️ `mmaaaa` = **mois + année de démarrage du projet**, pas la date de rendu.

### Fabrication

```bash
uv run python scripts/construire_rapport.py   # le PDF, si besoin
uv run python scripts/construire_archive.py   # l'archive complète
```

L'archive est écrite dans `outputs/livrables/`, hors du dépôt. Ce que chaque
entrée contient :

| Entrée | Contenu | Taille |
|---|---|---|
| `1_Dataset` | parquet SFT et DPO, export JSONL, carte du jeu de données | 12 Mo |
| `2_Modele` | adaptateur LoRA final, tokenizer, gabarit, carte de modèle | 67 Mo |
| `3_Endpoint` | Dockerfile, point d'entrée, fonction distante, procédure | 15 Ko |
| `4_CICD` | les deux workflows GitHub Actions | 3 Ko |
| `5_Rapport` | le PDF, 20 pages | 0,5 Mo |

Trois choses **n'y sont pas**, volontairement :

- **le modèle de base** (`Qwen3-1.7B-Base`, 3,4 Go) — il n'est pas à
  redistribuer, l'adaptateur se pose dessus après téléchargement ;
- **l'adaptateur de référence du DPO** — artefact interne au calcul de la
  divergence, sans usage pour qui reçoit le livrable, et aussi lourd que
  l'adaptateur utile ;
- **la clé d'accès au service** — elle se remet séparément.

## Checklist de rendu

- [x] **L1** — dataset versionné en parquet + [carte documentée](../data/processed/README.md)
- [x] **L2** — adaptateur publié sur
      [ClementRbl/triage-chsa-qwen3-1.7b](https://huggingface.co/ClementRbl/triage-chsa-qwen3-1.7b),
      67 Mo, avec sa carte de modèle, ses métriques et ses limites d'usage
- [x] **L3** — endpoint déployé et mesuré :
      <https://clement-rbl--triage-chsa-service.modal.run>
      (protégé par clé, latence p95 2 306 ms, journal d'audit persistant)
- [x] **L4** — workflows verts : lint, format, types, tests, intégrité des
      données, **et déploiement automatique** depuis `main`
- [x] **L5** — [rapport technique](../rapport/Reboul_Clement_5_Rapport_082026.pdf),
      **20 pages** sur 20 autorisées, fabriqué de façon reproductible
      (`uv run python scripts/construire_rapport.py`)
- [x] Archive zip nommée selon la convention, fabriquée de façon reproductible
      (`uv run python scripts/construire_archive.py`)

### Adresses des livrables en ligne

| Livrable | Adresse |
|---|---|
| L2 — modèle | <https://huggingface.co/ClementRbl/triage-chsa-qwen3-1.7b> |
| L3 — endpoint | <https://clement-rbl--triage-chsa-service.modal.run> |

L'endpoint exige l'en-tête `X-Cle-Api`. Procédure complète et rotation des
secrets : [`deploiement/README.md`](../deploiement/README.md).
