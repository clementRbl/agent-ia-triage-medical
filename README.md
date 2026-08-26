# Agent IA de triage médical — POC

Proof of Concept d'un agent d'aide au triage aux urgences : collecte des
symptômes, évaluation du niveau de priorité (urgence maximale / modérée /
différée), explication de la décision et traçabilité des interactions.

Modèle : **Qwen3-1.7B-Base**, spécialisé par **SFT + LoRA** puis aligné par
**DPO**, servi via **vLLM** derrière une API **FastAPI**.

> ⚠️ Outil d'**aide à la décision**. Il ne pose pas de diagnostic et ne remplace
> pas l'évaluation d'un professionnel de santé.

## Documentation

| Document | Contenu |
|---|---|
| [docs/00-contexte-mission.md](docs/00-contexte-mission.md) | Contexte, besoin métier, stratégie en 3 phases |
| [docs/01-livrables.md](docs/01-livrables.md) | Les 5 livrables et la convention de nommage |
| [docs/02-planning-4-semaines.md](docs/02-planning-4-semaines.md) | Feuille de route semaine par semaine |
| [docs/03-etape-1-donnees.md](docs/03-etape-1-donnees.md) | Collecte, anonymisation, RGPD, schéma de métadonnées |
| [docs/03b-inventaire-sources.md](docs/03b-inventaire-sources.md) | Inventaire vérifié des sources, licences, analyse de contenu |
| [docs/03c-plan-composition-dataset.md](docs/03c-plan-composition-dataset.md) | Composition chiffrée des jeux SFT et DPO, règles anti-fuite |
| [docs/03d-anonymisation-rgpd.md](docs/03d-anonymisation-rgpd.md) | Stratégie de masquage, contrôle qualité mesuré, traçabilité |
| [data/processed/README.md](data/processed/README.md) | Carte du jeu de données produit (schéma, volumes, licences, limites) |
| [docs/04-etape-2-sft-dpo.md](docs/04-etape-2-sft-dpo.md) | SFT + LoRA, alignement DPO, métriques |
| [docs/04b-resultats-entrainement.md](docs/04b-resultats-entrainement.md) | Résultats mesurés : SFT, évaluation clinique, investigation DPO |
| [docs/05-etape-3-deploiement.md](docs/05-etape-3-deploiement.md) | Docker, FastAPI, vLLM, CI/CD, go/no-go |
| [docs/06-glossaire.md](docs/06-glossaire.md) | Bases théoriques SFT / DPO et glossaire |
| [docs/99-decisions.md](docs/99-decisions.md) | Journal des décisions techniques |

## Jeu de données

`data/processed/` contient le livrable 1 : **5 000 paires SFT** bilingues et
**3 000 paires DPO**, au format parquet (natif Hugging Face Datasets).

```bash
# régénérer le JSONL
uv run python -c "from triage.data.build import exporter_jsonl; exporter_jsonl()"
```

Voir la [carte du jeu de données](data/processed/README.md).

## Exploration

```bash
uv run jupyter lab notebooks/01_exploration_corpus.ipynb
```

Le notebook caractérise les corpus et contrôle la chaîne d'anonymisation. Il
importe `src/triage/` : aucune logique n'y est dupliquée.

## Installation

```bash
uv sync
uv run pytest
```

## Intégration continue

Trois jobs GitHub Actions sur chaque PR ([.github/workflows/ci.yml](.github/workflows/ci.yml)) :

| Job | Contrôle |
|---|---|
| Lint et format | `ruff check` + `ruff format --check` sur tout le dépôt, notebooks compris |
| Tests | suite unitaire |
| Intégrité du jeu de données | empreintes des manifestes, seuil de PII résiduelle, absence de fuite entre les jeux |

## Modèle

`Qwen3-1.7B-Base` spécialisé par **SFT + LoRA** puis aligné par **DPO**.
Adaptateurs de 67 Mo chacun, entraînés sur une RTX 3080 de 10 Go.

| Sur 99 cas de triage jamais vus | Base | SFT | **SFT + DPO** |
|---|---|---|---|
| Exactitude | 0 % | 91,92 % | **92,93 %** |
| Sur-triage | — | 4,04 % | **3,03 %** |
| Urgences vitales identifiées | 0/31 | 31/31 | **31/31** |

Résultats détaillés, échecs compris :
[docs/04b-resultats-entrainement.md](docs/04b-resultats-entrainement.md).

```bash
# entraînement supervisé puis alignement
uv run python -c "from triage.training.sft import entrainer_sft; entrainer_sft()"
uv run python -c "from triage.training.dpo import entrainer_dpo; entrainer_dpo()"

# évaluation clinique : base, SFT, DPO sur les mêmes cas
uv run python scripts/evaluer_triage.py --dpo
uv run python scripts/evaluer_triage.py --dpo --generalisation

# suivi des runs
uv run mlflow ui --backend-store-uri sqlite:///mlflow.db
```

## État d'avancement

| Semaine | Objet | État |
|---|---|---|
| 1 | Préparation des données | ✅ 5 000 paires SFT + 3 000 paires DPO, anonymisées |
| 2 | Fine-tuning supervisé (SFT + LoRA) | ✅ 92,93 % d'exactitude, 0 urgence manquée |
| 3 | Alignement par préférences (DPO) | ✅ trois runs, ablation concluante |
| 4 | Déploiement et validation | ⏳ Docker, FastAPI, vLLM, cloud |

Décisions techniques et points ouverts :
[docs/99-decisions.md](docs/99-decisions.md).
