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
| [docs/04-etape-2-sft-dpo.md](docs/04-etape-2-sft-dpo.md) | SFT + LoRA, alignement DPO, métriques |
| [docs/05-etape-3-deploiement.md](docs/05-etape-3-deploiement.md) | Docker, FastAPI, vLLM, CI/CD, go/no-go |
| [docs/06-glossaire.md](docs/06-glossaire.md) | Bases théoriques SFT / DPO et glossaire |
| [docs/99-decisions.md](docs/99-decisions.md) | Journal des décisions techniques |

## État

Cadrage terminé. Stack technique en cours de validation — voir
[docs/99-decisions.md](docs/99-decisions.md).
