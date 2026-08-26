# 03d — Anonymisation et conformité RGPD

Ce document justifie le processus d'anonymisation exigé par l'étape 1 et rend
compte du **contrôle qualité du masquage** demandé.

## 1. Base légale et périmètre

Le POC n'utilise **aucune donnée patient réelle du CHSA**. Les corpus employés
sont des jeux publics de cas cliniques d'enseignement, déjà pseudonymisés par
leurs auteurs (« Madame X. », « Monsieur H. »).

La chaîne d'anonymisation est néanmoins implémentée et mesurée, pour deux
raisons :

1. **Défense en profondeur** — la pseudonymisation amont n'est pas garantie
   exhaustive : le contrôle a effectivement trouvé des patronymes complets
   (« Brigitte V. », « Mathilde M », « Monsieur V. Joseph »).
2. **Réutilisabilité** — c'est la brique qui devra traiter les données réelles
   du système d'information hospitalier en phase 2.

## 2. Outils

- **Presidio** (`presidio-analyzer`, `presidio-anonymizer`), recommandé par le
  cahier des charges.
- Modèles spaCy **`fr_core_news_md`** et **`en_core_web_md`**, épinglés dans
  `pyproject.toml` pour que la CI soit reproductible.

## 3. Stratégie de masquage : `replace`, et ciblé

Des trois stratégies possibles (`replace`, `mask`, `redact`), **`replace`** est
retenue, avec des marqueurs typés : `<PATIENT>`, `<DATE>`, `<NIR>`, `<EMAIL>`,
`<TELEPHONE>`, `<ETABLISSEMENT>`.

**Pourquoi pas `redact`** : la suppression pure casse la syntaxe de la phrase.
Le corpus sert à entraîner un modèle de langue — un texte agrammatical dégrade
l'apprentissage. **Pourquoi pas `mask`** : les suites de caractères de
remplissage n'apportent aucune information de type au modèle.

### Ce qui est retiré / ce qui est conservé

| Retiré | Conservé | Justification |
|---|---|---|
| Nom, prénom, civilité + patronyme | — | Identifiant direct |
| NIR (n° sécurité sociale) | — | Identifiant direct, donnée de santé |
| Email, téléphone, IBAN | — | Coordonnées |
| Date absolue (`12 mars 2024`) | **Durées** (`depuis 3 jours`) | La date situe la personne ; la durée d'évolution est un critère de triage |
| Nom d'établissement | — | Quasi-identifiant sans valeur clinique |
| — | **Localisation géographique** | Signal clinique majeur : masquer « Gabon » détruirait un cas de chimioprophylaxie du paludisme |
| Âge ≥ 90 ans → `90+` | **Âge < 90 ans** | L'âge détermine le triage ; les grands âges sont ré-identifiants (seuil repris du Safe Harbor HIPAA) |

> **Décision structurante** : ne pas masquer les localisations. C'est un écart
> assumé par rapport à un masquage générique, motivé par l'utilité clinique et
> par le fait que le corpus ne contient pas d'adresse de patient.

## 4. Le problème découvert : sur-masquage du vocabulaire médical

Le premier passage sur les 1 011 cas cliniques a produit **892 détections
`PERSON`**, dont la majorité sont des faux positifs :

| Catégorie | Exemples détectés à tort |
|---|---|
| Éponymes | Parkinson (10), Babinski (8), Senning (8), Kawasaki (4), Hashimoto (3) |
| Biologie | Hémoglobine, Leucocytes, Thrombocytes, Créatinine, Fibrinogène, Ionogramme |
| Signes cliniques | Cyanose, hépatosplénomégalie, nulligeste, céphaline |
| Médicaments | Persantine® |
| Symboles chimiques | Na, K, Sg |

Laisser faire aurait transformé « signe de **Babinski** » en « signe de
**\<PATIENT\>** » — une perte d'information clinique bien plus grave que le
risque résiduel de ré-identification.

### Filtre mis en place (`src/triage/data/lexique_medical.py`)

Quatre règles, du moins coûteux au plus coûteux :

1. Un patronyme français commence par une **majuscule** → les détections en
   minuscule sont écartées.
2. Un token d'**une seule lettre** n'identifie personne.
3. Le span figure dans un **lexique médical** (éponymes, analyses, signes,
   symboles chimiques) ou porte une marque déposée (`®`, `™`).
4. Le span suit un **déclencheur d'éponyme** (`maladie de`, `signe de`,
   `syndrome de`, `intervention de`, `indice de`…) — couvre les éponymes
   absents du lexique.

## 5. Contrôle qualité — résultats mesurés

Méthode : anonymiser, puis **ré-analyser la sortie**. Toute entité identifiante
encore détectée est comptée comme résidu.
Implémentation : `src/triage/data/qc_anonymisation.py`.
Corpus : les **1 011 cas cliniques uniques** de MediQAl `oeq`.

| Métrique | Sans filtre | **Avec filtre** |
|---|---|---|
| Détections `PERSON` | 892 | **534** |
| Faux positifs médicaux évités | — | **358** |
| Textes avec PII résiduelle | 14 (1,19 %) | **2 (0,20 %)** |

**Entités retirées au total** : PERSON 534, FR_CIVILITE 422,
ETABLISSEMENT_SANTE 226, FR_DATE_ABSOLUE 16, PHONE_NUMBER 4.
**49,7 %** des cas cliniques contenaient au moins une entité à masquer.

### Analyse des 2 résidus

Les deux détections restantes portent sur le **marqueur `<PATIENT>` lui-même**,
ré-identifié comme nom propre lorsqu'il est accolé à une unité de laboratoire
(`<PATIENT>/L`). Ce ne sont **pas des fuites** : aucune donnée personnelle
d'origine ne subsiste.

### Régression corrigée

Le contrôle a révélé une fuite réelle : « Monsieur V. Joseph » n'était masqué
que jusqu'à « Monsieur V. », laissant apparaître « Joseph ». L'expression
régulière de civilité capture désormais jusqu'à trois tokens de patronyme.
Test de non-régression : `tests/test_anonymize.py::test_patronyme_complet_apres_civilite`.

## 6. Traçabilité (auditabilité)

Chaque étape écrit un **manifeste JSON** dans `data/manifests/`
(`src/triage/audit.py`) contenant :

- l'étape, l'horodatage UTC et la **révision git du code** ;
- les fichiers d'entrée et de sortie avec leur **empreinte SHA-256** ;
- le nombre de lignes par fichier ;
- les paramètres et les statistiques de l'étape.

Un artefact est ainsi rattachable au code exact qui l'a produit.

## 7. Limites assumées

- Le lexique médical est **curatif, non exhaustif** : de nouveaux éponymes
  peuvent échapper au filtre. La règle de contexte (règle 4) limite l'impact.
- Le filtre accepte un léger **sur-masquage résiduel** dans les tableaux de
  résultats biologiques, sans conséquence clinique.
- Aucune **validation par un DPO ni par un clinicien** n'a été réalisée dans le
  cadre du POC — c'est un point de la roadmap avant tout traitement de données
  réelles.
