# 04b — Résultats d'entraînement et d'évaluation

Matériel : RTX 3080, **10 Go de VRAM**, partagée avec le bureau graphique
(~700 Mo occupés par Xorg, Firefox et Docker Desktop).

## 1. Fine-tuning supervisé (SFT + LoRA)

| | |
|---|---|
| Modèle | `Qwen/Qwen3-1.7B-Base` |
| Méthode | LoRA r=16, α=32, dropout 0,05, 7 projections par bloc |
| Paramètres entraînés | **17,4 M / 1,74 Md = 1,003 %** |
| Lot effectif | 16 (2 × accumulation 8) |
| Fenêtre | 1 024 tokens |
| Durée | **41 min 33 s** (500 pas, 2 époques) |
| VRAM au pic | **5,99 Go** |
| Adaptateur produit | **67 Mo** |
| Perte finale | train 1,3526 · validation 1,3576 |

### Dimensionnement mesuré, pas supposé

- **Fenêtre** : p50 à 332 tokens, p99 à 988. À 1 024, **0,66 %** des exemples
  sont tronqués ; 1 536 n'en récupérerait que 0,64 % de plus pour 50 %
  d'activations en sus.
- **VRAM** : sonde préalable sur les 32 exemples les plus longs → pic 5,99 Go,
  4,35 Go de marge. Aucun dépassement en cours de run.
- **Taille de lot** : un lot de 4 tient en mémoire (6,26 Go) mais **ne change
  pas le débit** — l'entraînement est limité par le calcul, pas par les
  lancements de noyaux. Le lot de 2 est conservé pour la marge.

### Convergence

| Pas | 50 | 100 | 200 | 300 | 400 | 450 | 500 |
|---|---|---|---|---|---|---|---|
| `eval_loss` | 1,5385 | 1,4516 | 1,3899 | 1,3685 | 1,3579 | 1,3587 | 1,3576 |

La perte de validation **plafonne dès le pas 400**, soit 1,6 époque. Les cent
derniers pas gagnent 0,0003. Aucune remontée : **pas de sur-apprentissage**,
ce qui répond au point de vigilance du cahier des charges. Pour les runs
suivants, 1,6 époque suffit et économise ~8 minutes.

## 2. Évaluation clinique

99 cas de triage du split de test, jamais vus à l'entraînement
(42 différés, 31 maximales, 26 modérées ; 54 fr / 45 en). Génération
déterministe, sans échantillonnage, pour que deux exécutions donnent le même
résultat.

### Métriques retenues

Le **taux de sous-triage critique** — part des urgences maximales minorées —
est rapporté séparément de l'exactitude. Encombrer le service et laisser un
patient grave en salle d'attente n'ont pas la même conséquence, et une réponse
hors format est comptée à part plutôt que rattachée à une classe.

### Résultats

| | Base | **SFT** |
|---|---|---|
| Exactitude | 0,00 % | **91,92 %** |
| Sous-triage | — | 4,04 % |
| Sur-triage | — | 4,04 % |
| Réponses hors format | **100,00 %** | 0,00 % |
| **Urgences identifiées** | 0/31 | **31/31** |

Matrice du SFT :

```
réel = maximale (31)  →  31 maximale                          100 %
réel = différée (42)  →  42 différée                          100 %
réel = modérée  (26)  →  18 modérée, 4 maximale, 4 différée
```

**Les huit erreurs portent toutes sur la classe intermédiaire.** Aucune urgence
vitale n'est manquée. Le modèle de base, lui, ne produit aucun niveau
exploitable : l'apport du SFT n'est pas une amélioration marginale mais le
passage d'inutilisable à exploitable.

### Généralisation à des motifs jamais vus

Le jeu de test réutilise les douze motifs de recours de l'entraînement : un
modèle peut y exceller en retenant la forme des cas. Six motifs supplémentaires
— crise convulsive, hémorragie digestive, brûlure, intoxication médicamenteuse,
douleur scrotale aiguë, polytraumatisme — n'entrent **jamais** dans
l'entraînement et servent uniquement à l'évaluation.

| | Motifs vus | Motifs inédits |
|---|---|---|
| Exactitude | 91,92 % | 87,50 % |
| Sous-triage global | 4,04 % | 5,83 % |
| Sur-triage | 4,04 % | 6,67 % |
| **Urgences minorées** | **0/31 — 0 %** | **5/40 — 12,5 %** |

L'exactitude globale ne perd que 4,4 points : le modèle a donc bien appris à
**lire des constantes vitales**, pas seulement à reconnaître douze gabarits.

Mais le mode de défaillance dangereux **n'apparaît que hors des gabarits
connus**. L'exactitude seule ne l'aurait jamais montré — 87,5 % a l'air très
bien. C'est l'argument central en faveur d'une évaluation sur motifs réservés.

## 3. Alignement par préférences (DPO)

Trois runs, documentés ici parce que les deux échecs sont plus instructifs que
le résultat.

### Run 1 — préférences unidirectionnelles

Toutes les paires de triage rejetaient une réponse **minorant** la priorité,
dans l'intention de combattre le sous-triage.

| | SFT | DPO run 1 |
|---|---|---|
| Exactitude | 91,92 % | **42,42 %** |
| Sur-triage | 4,04 % | **57,58 %** |

Le modèle classait 95 % des prises en charge différées en urgence. La cause est
structurelle : sous une distribution où la réponse plus basse est *toujours* la
mauvaise, la politique optimale est d'annoncer toujours le niveau le plus haut.
Les cas déjà différés étaient de surcroît écartés du jeu, supprimant le dernier
contre-exemple possible.

**À retenir** : un signal de préférence unidirectionnel enseigne une consigne
triviale, pas une décision.

### Run 2 — préférences équilibrées

Chaque niveau produit l'erreur ou les erreurs qui lui sont possibles ; le jeu
passe à 1 000 paires de triage, réparties 501 sous-triage / 499 sur-triage.

| | SFT | DPO run 2 |
|---|---|---|
| Exactitude | 91,92 % | 64,65 % |
| **Urgences manquées** | **0/31** | **13/31 (42 %)** |

Le biais « toujours plus haut » disparaît, mais le résultat est pire sur la
métrique de sécurité. L'inspection des sorties montre pourquoi :

```
Constantes : FR 5/min   (critère réel : « FR > 30/min ou < 8/min »)

SFT   URGENCE MAXIMALE · fréquence respiratoire > 30/min ou < 8/min (FR 5/min)
DPO   URGENCE MODÉRÉE  · fréquence respiratoire entre 25 et 30/min (FR 5/min)
```

Le modèle a appris à **permuter l'étiquette du critère en même temps que le
niveau**, tout en conservant la valeur mesurée. Il produit des réponses
incohérentes avec elles-mêmes : « urgence modérée » assortie de
« PAS < 90 mmHg », qui est un critère d'urgence maximale.

Le mécanisme : les réponses choisie et rejetée partagent environ 90 % de leurs
tokens, donc le gradient se concentre sur les rares tokens qui diffèrent — les
étiquettes. Le modèle apprend que celles-ci sont permutables indépendamment de
la valeur qu'elles décrivent.

Second dégât observé : **contamination linguistique**. Des fragments anglais
apparaissent dans les réponses françaises (« réévaluation des constantes *every
30 minutes* »), les deux tiers des paires de préférence étant anglophones.

### Hypothèse

Le triage possède une **vérité terrain déterministe** : le niveau se déduit de
règles. Le DPO est conçu pour des tâches où la qualité est subjective — utilité,
ton, pertinence d'une explication. L'appliquer à une décision vérifiable revient
à substituer une préférence relative à une réponse juste, et introduit du bruit
là où le SFT avait convergé.

### Run 3 — ablation

DPO sur les seules paires UltraMedical, **sans aucune paire de triage**
(2 000 paires). Objectif : distinguer l'effet des paires de triage de celui des
données anglophones.

*(résultats à compléter)*
