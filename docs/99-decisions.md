# 99 — Journal des décisions techniques (ADR light)

Une ligne par décision : date, décision, alternatives écartées, raison.
Ce journal alimente directement la section « méthodologie » du rapport final.

## Décidé

| Date | Décision | Raison |
|---|---|---|
| 2026-08-20 | Modèle de base : **Qwen3-1.7B-Base** | Imposé par le cahier des charges |
| 2026-08-20 | Adaptation : **LoRA** puis **DPO** | Imposé par le cahier des charges |
| 2026-08-20 | Serving : **vLLM** derrière **FastAPI**, conteneurisé Docker | Imposé par le cahier des charges |
| 2026-08-20 | CI/CD : **GitHub Actions** | Imposé par le cahier des charges |
| 2026-08-20 | Paquets **uv**, lint/format **ruff**, tests **pytest** | Standards du poste de travail |
| 2026-08-20 | Framework d'entraînement : **TRL + PEFT** (`SFTTrainer`, `DPOTrainer`) | Stack HF standard, méthodologie facile à défendre en soutenance, DPO natif ; suffisant pour 1,7B sur 10 Go |
| 2026-08-20 | Tracking : **Weights & Biases** | Intégration TRL immédiate, courbes exportables dans le rapport PDF |
| 2026-08-20 | Données : **corpus imposés + cas de triage synthétiques** | Aucun des 4 corpus n'est un dataset de triage ; les corpus servent de socle de connaissance, les cas synthétiques (symptômes/antécédents/constantes → priorité, grille FRENCH/CIMU) remplissent le schéma de métadonnées exigé. **Limite à documenter explicitement dans le rapport.** |

| 2026-08-20 | Sources retenues : **MediQAl** (CC-BY-4.0, FR) + **UltraMedical-Preference** (MIT, EN) | MediQA, FrenchMedMCQA et MedQuAD ne sont plus accessibles ; les deux sources retenues couvrent le périmètre bilingue et les préférences. Voir [03b](03b-inventaire-sources.md) |
| 2026-08-20 | Splits **par `clinical_case`** et partition des `prompt_id` | Plusieurs questions partagent un même cas clinique → un split par ligne provoquerait une fuite train/éval |
| 2026-08-20 | Exclusion des paires DPO `label_type == "length"` | Biais de longueur connu, fausserait l'alignement |

| 2026-08-20 | Découpage **par groupe** via empreinte du `clinical_case` | Affectation déterministe et stable quand le corpus grandit ; un découpage ligne à ligne ferait fuiter un même cas entre train et test |
| 2026-08-20 | CI mise en place dès la semaine 1 | Garde toutes les PR suivantes et avance le livrable 4 |
| 2026-08-20 | Notebook d'exploration important `src/`, sans logique propre | Reproductibilité : les mêmes traitements tournent en exploration, en production et sous CI |

| 2026-08-26 | Bloc C et DPO tirés d'UltraMedical via **viviers disjoints** (35/50/15) | Un même prompt ne peut pas servir au SFT, au DPO et à l'évaluation |
| 2026-08-26 | Barème de triage **par règles explicites**, label déduit et non choisi | Une règle fausse devient un bug détectable par un test, au lieu d'une erreur diffuse dans 1 000 exemples |
| 2026-08-26 | Réponses `rejected` de sous-triage **cohérentes avec elles-mêmes** | Une réponse qui annonce un niveau bas tout en listant les critères de gravité serait trop facile à écarter pour apporter quoi que ce soit à l'alignement |
| 2026-08-26 | Parquet versionné, JSONL régénérable | Le parquet est le format natif HF Datasets et pèse 8 Mo contre 22 Mo pour le JSONL |

## À trancher

| Sujet | Options | Statut |
|---|---|---|
| Hébergement de l'endpoint | RunPod / Scaleway / HF Endpoints / autre | ⏳ à trancher avant S4 |
| ~~Volume du jeu DPO~~ | 2 667 paires produites | ✅ tranché |
| Hébergement du dataset | HF Hub (public/privé) / repo git + LFS | ⏳ |
| Vérificateur de types | `ty` (Astral) / `mypy` | ⏳ job CI à ajouter une fois choisi |
