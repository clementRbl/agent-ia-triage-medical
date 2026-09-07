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
| [docs/05-etape-3-deploiement.md](docs/05-etape-3-deploiement.md) | Architecture du service, garde-fou, traçabilité, go/no-go |
| [deploiement/README.md](deploiement/README.md) | Procédure de déploiement, secrets, routes de l'API |
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

Trois jobs sur chaque PR ([.github/workflows/ci.yml](.github/workflows/ci.yml)) :

| Job | Contrôle |
|---|---|
| Lint, format et types | `ruff check`, `ruff format --check` et `ty check` sur tout le dépôt, notebooks compris |
| Tests | 208 tests unitaires |
| Intégrité du jeu de données | empreintes des manifestes, seuil de PII résiduelle, absence de fuite entre les jeux |

Un quatrième workflow ([deploiement.yml](.github/workflows/deploiement.yml))
redéploie depuis `main` quand la CI y est verte, puis mesure latence,
robustesse et traçabilité sur le service déployé. Livrer une version dont les
tests n'ont pas été rejoués reviendrait à mettre en service un modèle de
triage non vérifié.

## Modèle

`Qwen3-1.7B-Base` spécialisé par **SFT + LoRA** puis aligné par **DPO**.
Adaptateurs de 67 Mo chacun, entraînés sur une RTX 3080 de 10 Go.

Adaptateur publié :
**[ClementRbl/triage-chsa-qwen3-1.7b](https://huggingface.co/ClementRbl/triage-chsa-qwen3-1.7b)**

**Jeu de test** — 99 cas, motifs de recours vus à l'entraînement :

| | Base | SFT | **SFT + DPO** |
|---|---|---|---|
| Exactitude | 0 % | 91,92 % | **92,93 %** |
| Sur-triage | — | 4,04 % | **3,03 %** |
| Urgences vitales identifiées | 0/31 | 31/31 | **31/31** |

**Jeu de généralisation** — 600 cas, 200 urgences, 14 motifs *jamais vus* :

| | SFT | **SFT + DPO** |
|---|---|---|
| Exactitude | 89,50 % [86,8 – 91,7] | **90,17 %** [87,5 – 92,3] |
| **Sous-triage critique** | 8,50 % [5,4 – 13,2] | **8,50 %** [5,4 – 13,2] |

L'écart entre les deux modèles n'est pas significatif (test apparié, p = 0,42).
Le chiffre qui compte est le second : **17 urgences vitales sur 200 sont
annoncées à un niveau moindre**. C'est pourquoi le service ne sert jamais le
modèle seul — un barème explicite relève la priorité en cas de désaccord.

Résultats détaillés, échecs compris :
[docs/04b-resultats-entrainement.md](docs/04b-resultats-entrainement.md).

```bash
# entraînement supervisé puis alignement
uv run python -c "from triage.training.sft import entrainer_sft; entrainer_sft()"
uv run python -c "from triage.training.dpo import entrainer_dpo; entrainer_dpo()"

# évaluation clinique : base, SFT, DPO sur les mêmes cas
uv run python scripts/evaluer_triage.py --dpo
uv run python scripts/evaluer_triage.py --dpo --generalisation

# intervalles de confiance et comparaison appariée des deux modèles
uv run python scripts/intervalles_confiance.py

# suivi des runs
uv run mlflow ui --backend-store-uri sqlite:///mlflow.db
```

## Service déployé

**<https://clement-rbl--triage-chsa-service.modal.run>** — endpoint servi par
vLLM sur GPU, protégé par l'en-tête `X-Cle-Api`.

| | Médiane | p95 |
|---|---|---|
| Séquentiel (24 appels) | 1 854 ms | 2 306 ms |
| 8 requêtes en parallèle | 1 955 ms | 2 532 ms |

Huit requêtes simultanées ne coûtent que **6 % de latence médiane** : c'est
l'apport du traitement par lots continu de vLLM.

```bash
# en local, sans GPU : le barème répond à la place du modèle
TRIAGE_MOTEUR=regles uv run uvicorn triage.api.app:app --reload --port 8080

# mesures sur le service déployé : latence, robustesse, traçabilité
TRIAGE_CLE_API=<clé> uv run python scripts/mesurer_service.py \
  --url https://clement-rbl--triage-chsa-service.modal.run
```

Trois dispositifs de sécurité, chacun couvert par des tests :

- **Questionnaire adaptatif** — les signes de gravité dépistés dépendent du
  motif, et le recueil s'arrête dès qu'un critère d'urgence maximale est
  rempli. La règle d'arrêt est déterministe, jamais laissée au modèle.
- **Garde-fou** — quand le modèle annonce moins grave que le barème, la
  priorité est relevée et l'écart consigné. Quand il annonce plus grave, sa
  prudence est conservée.
- **Journal chaîné** — chaque entrée porte l'empreinte de la précédente.
  Modification, suppression, insertion et réordonnancement sont détectés.

Documentation interactive de l'API sur `/docs`, procédure complète dans
[deploiement/README.md](deploiement/README.md).

## État d'avancement

| Semaine | Objet | État |
|---|---|---|
| 1 | Préparation des données | ✅ 5 000 paires SFT + 3 000 paires DPO, anonymisées |
| 2 | Fine-tuning supervisé (SFT + LoRA) | ✅ 92,93 % d'exactitude, 0 urgence manquée |
| 3 | Alignement par préférences (DPO) | ✅ trois runs, ablation concluante |
| 4 | Déploiement et validation | ✅ endpoint public mesuré, Docker, livraison continue |
| 4 | Évaluation élargie | ✅ 600 cas, 200 urgences, intervalles de confiance |
| — | Rapport technique (L5) | ✅ [20 pages](rapport/Reboul_Clement_5_Rapport_082026.pdf) |

Décisions techniques et points ouverts :
[docs/99-decisions.md](docs/99-decisions.md).
