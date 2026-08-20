# 03b — Inventaire vérifié des sources (2026-08-20)

## Vérification des 4 sources du cahier des charges

| Source demandée | Statut | Décision |
|---|---|---|
| **MediQA** | ❌ introuvable en l'état | Remplacée par **MediQAl** |
| **FrenchMedMCQA** | ❌ introuvable en l'état | Couverte par **MediQAl** (`mcqu`/`mcqm` = QCM médicaux FR) |
| **MedQuAD** | ❌ introuvable en l'état | Couverte par **UltraMedical-Preference** (Q/R médicales EN) |
| **UltraMedical-Preference** | ✅ disponible | Conservée |

> À justifier dans le rapport : deux des quatre corpus cités n'étaient plus
> accessibles au démarrage. Le périmètre bilingue et la nature des données
> (QCM FR + Q/R EN + préférences) sont intégralement préservés par les deux
> sources retenues.

## Source 1 — `ANR-MALADES/MediQAl` (français)

- **URL** : <https://huggingface.co/datasets/ANR-MALADES/MediQAl>
- **Licence** : **CC-BY-4.0** → redistribution autorisée **avec attribution**
- **Producteur** : projet ANR MALADES

| Config | Split | Lignes | Nature |
|---|---|---|---|
| `oeq` | test | 4 969 | Questions ouvertes sur cas cliniques (1 011 cas uniques) |
| `mcqu` | train / val / test | 10 113 / 2 561 / 4 343 | QCM à réponse unique |
| `mcqm` | train / val / test | 5 767 / 1 466 / 3 384 | QCM à réponses multiples |

**Champs `oeq`** : `id`, `clinical_case`, `cc_question_number`, `question`,
`answer`, `medical_subject`, `question_type`
**Champs `mcqu`/`mcqm`** : + `answer_a..e`, `correct_answers`, `task`

### Analyse de contenu (mesurée, pas supposée)

Sur les **1 011 cas cliniques uniques** de `oeq` :

| Signal | Couverture |
|---|---|
| Âge du patient | **68 %** |
| Civilité (M./Mme/Monsieur/Madame) | **27 %** |
| Antécédents (ATCD / « antécédents ») | **24 %** |
| Constantes vitales structurées (`FC =`, `SpO2 =`…) | **1 %** |

Longueur médiane : cas 572 caractères, réponse 176 caractères.
`question_type` : Reasoning 3 125 / Understanding 1 842.

Répartition par spécialité (`oeq`) : Pharmacy 1 544, Pediatric Cardiology 1 225,
Cardiology 217, Nephro-Urology 193, Pulmonology 184, Intensive Care 154,
Neurology 150, … **Emergency Medicine 109**.

Dans `mcqu` train, **6 178 / 10 113 lignes n'ont pas de cas clinique** (question
de connaissance pure) ; les ~3 900 restantes en ont un.

### Conséquences directes

1. ✅ **Presidio est réellement nécessaire** : 27 % des cas contiennent une
   civilité et un nom partiel (« Monsieur R. »), 68 % un âge. Le masquage n'est
   pas un exercice de style.
2. ⚠️ **Les constantes vitales sont quasi absentes** (1 %). Le champ
   `constantes` du schéma de métadonnées ne peut donc **pas** être rempli par
   extraction depuis MediQAl seul.
3. ⚠️ **Le corpus n'est pas un corpus de triage** : pas de label de priorité,
   et l'urgence ne représente qu'une fraction des spécialités. Les 3 niveaux
   (max / modérée / différée) doivent être construits.
4. ℹ️ `oeq` n'existe qu'en split `test` chez l'éditeur → **re-splitter
   nous-mêmes** train/val/test, en découpant **par `clinical_case`** et non par
   ligne, sinon fuite entre splits (plusieurs questions partagent un même cas).

## Source 2 — `TsinghuaC3I/UltraMedical-Preference` (anglais)

- **URL** : <https://huggingface.co/datasets/TsinghuaC3I/UltraMedical-Preference>
- **Licence** : **MIT** → redistribution libre
- **Volume** : `train` 994 Mo, `dev` 20 Mo, `test` 5,6 Mo (JSON)

**Champs** : `prompt`, `chosen`, `rejected`, `feedback`, `metadata`,
`prompt_id`, `label_type`

- `chosen` / `rejected` : listes de messages au format conversationnel
- `metadata` : pour chaque branche, `model`, `rank`, `score`, `evaluation`
- `prompt_id` : trace la sous-source (ex. `WikiInstruct,8304`)
- `label_type` : **⚠️ point de vigilance** — la valeur `length` signale une paire
  départagée sur un critère de longueur, biais connu du DPO. **À filtrer ou à
  sous-échantillonner**, et à documenter.

### Double usage

- **DPO** : source directe des paires chosen/rejected (usage prévu au cahier des charges).
- **SFT** : les réponses `chosen` fournissent aussi un socle de Q/R médicales
  anglophones de qualité — **à condition de partitionner les `prompt_id` en
  amont** pour qu'aucun prompt utilisé en SFT ne réapparaisse en DPO ni en
  évaluation.

## Attribution à faire figurer dans la carte de dataset

- MediQAl — ANR-MALADES — CC-BY-4.0 — citation de l'article source
- UltraMedical-Preference — TsinghuaC3I — MIT
