---
language:
  - fr
  - en
license: cc-by-4.0
task_categories:
  - text-generation
tags:
  - medical
  - triage
  - emergency-medicine
  - sft
  - dpo
size_categories:
  - 1K<n<10K
---

# Corpus bilingue d'aide au triage médical

Jeu de données construit pour le POC d'agent d'aide au triage des urgences du
Centre Hospitalier Saint-Aurélien. Deux jeux : **SFT** (5 000 paires
instruction-réponse) et **DPO** (3 000 paires préférentielles).

> ⚠️ **Usage** : recherche et démonstration. Ce corpus ne constitue pas une
> référence clinique. Le barème de triage n'a pas été validé par un clinicien.

## Jeu SFT — 5 000 paires

| Bloc | Source | Langue | Volume |
|---|---|---|---|
| A — raisonnement clinique | MediQAl `oeq` | fr | 2 000 |
| B — connaissance médicale | MediQAl `mcqu` + `mcqm` | fr | 1 000 |
| C — socle anglophone | UltraMedical-Preference (`chosen`) | en | 1 000 |
| D — triage structuré | règles explicites | fr 637 / en 363 | 1 000 |

**Langues** : 3 637 fr (73 %) · 1 363 en (27 %)
**Splits** : train 3 986 · validation 488 · test 526
**Longueur médiane** : instruction 595 caractères, réponse 326

## Jeu DPO — 3 000 paires

| Type | Volume | Origine |
|---|---|---|
| `hard` | 1 323 | UltraMedical, préférence difficile |
| `easy` | 677 | UltraMedical, préférence nette |
| `sous_triage` | 501 | construit : la réponse rejetée minore la priorité |
| `sur_triage` | 499 | construit : la réponse rejetée majore la priorité |

**Splits** : train 2 394 · validation 302 · test 304

Les paires étiquetées `length` par la source sont **exclues** : elles sont
départagées sur la longueur de la réponse, biais connu qui apprendrait au
modèle à être bavard plutôt que juste.

### Les deux sens d'erreur sont représentés

Une première version ne rejetait que des réponses **minorant** la priorité, en
visant le sous-triage. Le signal était alors unidirectionnel, et un modèle
entraîné dessus a appris la consigne triviale « annonce toujours le niveau le
plus haut » : 57 % de sur-triage, exactitude tombée de 91,9 % à 42,4 %.

Chaque niveau produit donc l'erreur ou les erreurs qui lui sont possibles : une
urgence maximale ne peut être que minorée, une prise en charge différée que
majorée, un cas modéré alterne entre les deux.

Les contre-exemples imitent des erreurs réelles. Le sous-triage annonce un
niveau bas *et* déclare des constantes normales — les critères n'ont pas été
relevés. Le sur-triage cite les critères réellement remplis mais en tire une
conclusion trop grave, ou majore sans aucun critère objectivable.

> ⚠️ **À lire avant d'utiliser les paires de triage.** Elles portent sur une
> décision à **vérité terrain déterministe**, ce qui ne convient pas au DPO.
> Entraîner dessus dégrade le modèle, y compris avec un signal équilibré
> (13 urgences vitales manquées sur 31). Elles sont conservées pour la
> reproductibilité de l'expérience, documentée dans
> `docs/04b-resultats-entrainement.md`. Le modèle livré est aligné sur les
> seules paires UltraMedical.

## Schéma

| Champ | Description |
|---|---|
| `id`, `source`, `source_id`, `licence` | traçabilité de l'origine |
| `langue` | `fr` / `en` |
| `instruction`, `reponse` | la paire (SFT) |
| `prompt`, `chosen`, `rejected` | la paire préférentielle (DPO) |
| `bloc` | bloc de composition A/B/C/D |
| `symptomes`, `antecedents`, `constantes` | métadonnées cliniques |
| `niveau_priorite` | `maximale` / `moderee` / `differee` |
| `niveau_confiance` | 0–1, reflète la fiabilité de l'annotation |
| `anonymise`, `transformations` | trace des traitements appliqués |
| `groupe`, `split` | clé de découpage et affectation |

## Anonymisation

Presidio + spaCy (`fr_core_news_md`, `en_core_web_md`), masquage **ciblé** par
marqueurs typés. Entités retirées sur les 4 000 enregistrements issus de corpus :

| Entité | Occurrences |
|---|---|
| `PERSON` | 5 584 |
| `FR_CIVILITE` | 1 128 |
| `ETABLISSEMENT_SANTE` | 904 |
| `FR_DATE_ABSOLUE` | 62 |
| `PHONE_NUMBER` | 16 |

**PII résiduelle mesurée : 0,20 %**, sans fuite réelle.

Les localisations géographiques et les durées d'évolution sont **conservées** :
elles portent le signal clinique. Détail et justification dans
`docs/03d-anonymisation-rgpd.md`.

## Absence de fuite

- Découpage **par groupe** (cas clinique, prompt d'origine), jamais ligne à ligne.
- Les prompts UltraMedical sont répartis en trois viviers disjoints —
  SFT 35 %, DPO 50 %, évaluation 15 % — par empreinte de l'identifiant.
- Contrôle automatisé en intégration continue.

## Licences des sources

| Source | Licence | Volume SFT |
|---|---|---|
| [ANR-MALADES/MediQAl](https://huggingface.co/datasets/ANR-MALADES/MediQAl) | CC-BY-4.0 | 3 000 |
| [TsinghuaC3I/UltraMedical-Preference](https://huggingface.co/datasets/TsinghuaC3I/UltraMedical-Preference) | MIT | 1 000 |
| Cas de triage construits | règles explicites | 1 000 |

L'ensemble est redistribué sous **CC-BY-4.0**, la plus restrictive des licences
sources.

## Limites

- Le barème de triage est une transposition simplifiée de l'échelle FRENCH,
  **non validée cliniquement**.
- Les cas du bloc D sont construits à partir de 12 motifs de recours : leur
  diversité lexicale est inférieure à celle de cas réels.
- Le bloc B ne comporte pas de justification : les corpus sources n'en
  fournissent pas.
- L'urgence est sous-représentée dans les corpus d'origine (5,3 % des questions).
- Les paires de préférence portant sur le triage **ne doivent pas servir à
  l'alignement** (voir l'avertissement ci-dessus).

## Reproduction

```bash
uv sync
uv run python -c "from triage.data.ingest import telecharger; telecharger('mediqal')"
uv run python -c "from triage.data.build import construire_sft, construire_jeu_dpo, exporter_jsonl; construire_sft(); construire_jeu_dpo(); exporter_jsonl()"
```

Chaque étape écrit un manifeste horodaté dans `data/manifests/` : empreintes
SHA-256, volumes, paramètres et révision git du code.
