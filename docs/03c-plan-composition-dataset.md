# 03c — Plan de composition du dataset (L1)

Objectif : **5 000 paires SFT** bilingues + un jeu **DPO**, sans fuite entre
entraînement et évaluation.

## Jeu SFT — 5 000 paires

| Bloc | Source | Langue | Volume | Rôle |
|---|---|---|---|---|
| A — Raisonnement clinique | MediQAl `oeq` | FR | **2 000** | Q/R ouvertes sur cas réels : ancre le modèle sur le style clinique français |
| B — Connaissance médicale | MediQAl `mcqu` + `mcqm` | FR | **1 000** | QCM reformatés en instruction-réponse *avec justification*, pas en lettre nue |
| C — Socle anglophone | UltraMedical `chosen` | EN | **1 000** | Assure le bilinguisme exigé + qualité de rédaction |
| D — **Triage structuré** | Cas construits | FR + EN | **1 000** | Le seul bloc portant réellement `symptômes / antécédents / constantes → priorité` |
| | | | **5 000** | |

### Pourquoi le bloc D est indispensable

Aucune des deux sources ne porte de label de priorité ni de constantes vitales
exploitables (cf. [03b](03b-inventaire-sources.md)). Sans le bloc D :

- le champ `niveau_priorite` du schéma de métadonnées reste vide ;
- impossible de mesurer le **taux de sous-triage**, la métrique de sécurité
  centrale du projet ;
- l'agent ne sait pas produire les 3 niveaux demandés par le client.

**Méthode du bloc D** : cas construits à partir d'une grille de tri reconnue
(FRENCH / CIMU), en réutilisant les tableaux cliniques réels de MediQAl comme
matière première plutôt qu'en inventant *ex nihilo*. Chaque cas porte
symptômes, antécédents, constantes vitales et niveau de priorité motivé.

**À documenter comme limite du POC** : ces labels ne sont pas validés par un
clinicien du CHSA. C'est un point de la roadmap (validation par le comité
médical avant toute phase 2).

## Jeu DPO

- Base : **UltraMedical-Preference**, avec **exclusion des paires
  `label_type == "length"`** (biais de longueur).
- Complément **triage** : pour chaque cas du bloc D, une réponse `chosen`
  (priorité correcte + justification + orientation) et une réponse `rejected`
  illustrant une erreur réaliste — **prioritairement du sous-triage**, l'erreur
  la plus dangereuse.
- Volume cible à calibrer en S3 selon le budget GPU (1 000 à 3 000 paires
  suffisent largement pour un DPO sur 1,7B).

## Règles anti-fuite (exigence « ne pas mélanger train et éval »)

1. **Split par `clinical_case`**, jamais par ligne — plusieurs questions
   partagent un même cas dans `oeq`.
2. **Partition des `prompt_id`** UltraMedical en 3 pools disjoints :
   SFT / DPO / évaluation. Un prompt n'apparaît que dans un seul.
3. **Jeu d'évaluation clinique gelé** dès la semaine 1, jamais réouvert.
4. Contrôle automatisé de non-recouvrement (test `pytest`) exécuté en CI.

## Splits

| Split | Part | Usage |
|---|---|---|
| `train` | 80 % | SFT puis DPO |
| `validation` | 10 % | suivi de la perte, sélection de checkpoint |
| `test` | 10 % | métriques rapportées |
| `eval_clinique` | jeu séparé et gelé | sous-triage, hallucinations, sécurité |

## Traçabilité (auditabilité exigée)

Chaque enregistrement conserve `source`, `source_id`, `licence`, `lang`,
`transformations[]` (liste ordonnée des traitements appliqués, dont
l'anonymisation Presidio) et `anonymise`. Chaque étape du pipeline écrit un
manifeste : hash d'entrée, hash de sortie, nombre de lignes, version du script.
