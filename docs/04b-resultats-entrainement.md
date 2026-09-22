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
l'entraînement et servent uniquement à l'évaluation. *(Ces motifs réservés sont
passés à quatorze lors de l'élargissement décrit en 4 bis ; les chiffres de
cette section portent sur les six d'origine.)*

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

### Run 3 — ablation : DPO sans les paires de triage

DPO sur les seules paires UltraMedical (2 000 paires), **sans aucune paire de
triage**. Objectif : distinguer l'effet des paires de triage de celui des
données anglophones.

Signal visible dès l'entraînement — le modèle s'écarte beaucoup moins du SFT :

| | DPO avec triage | DPO ablation |
|---|---|---|
| `rewards/chosen` | −0,279 | **−0,048** |
| `rewards/margins` | 2,09 | 0,60 |

#### Résultats sur le jeu de test (99 cas)

| | Base | SFT | DPO run 1 | DPO run 2 | **DPO ablation** |
|---|---|---|---|---|---|
| Exactitude | 0 % | 91,92 % | 42,42 % | 64,65 % | **92,93 %** |
| Sous-triage | — | 4,04 % | 0 % | 14,14 % | 4,04 % |
| Sur-triage | — | 4,04 % | 57,58 % | 21,21 % | **3,03 %** |
| Urgences identifiées | 0/31 | 31/31 | 31/31 | 18/31 | **31/31** |

**Hypothèse confirmée.** Les paires portant sur la décision de triage étaient la
cause des deux échecs, et non les données anglophones — la contamination
linguistique observée au run 2 provenait donc, elle aussi, de la dérive globale
provoquée par un signal contradictoire.

Débarrassé de ces paires, le DPO améliore légèrement le SFT (+1,01 point,
sur-triage ramené de 4,04 % à 3,03 %) **sans toucher à la propriété de
sécurité** : aucune urgence vitale manquée.

## 4. Robustesse du modèle final

Sur les six motifs de recours jamais vus à l'entraînement :

| | SFT | DPO ablation |
|---|---|---|
| Exactitude | 87,50 % | 85,83 % |
| Sous-triage global | 5,83 % | 8,33 % |
| Sur-triage | 6,67 % | 5,83 % |
| Urgences minorées | 5/40 | 7/40 |

Le DPO gagne 1,01 point sur le jeu de test et en perd 1,67 sur les motifs
inédits. Avant d'en conclure quoi que ce soit, il faut mesurer la précision de
ces chiffres.

### Ces écarts ne sont pas significatifs

| Modèle | Urgences minorées | IC 95 % |
|---|---|---|
| SFT | 5/40 = 12,5 % | **[5,5 % – 26,1 %]** |
| DPO ablation | 7/40 = 17,5 % | **[8,7 % – 32,0 %]** |

Comparaison appariée sur les mêmes 40 cas : **2 paires discordantes**, toutes en
faveur du SFT, test binomial bilatéral **p ≈ 0,50**. L'écart tient à deux cas et
n'est pas distinguable du bruit.

### Conséquence pour la décision de déploiement

Avec 40 urgences évaluées, l'intervalle de confiance du taux de sous-triage
critique s'étend de 5,5 % à 26,1 %. **Aucun seuil d'acceptation clinique ne peut
être fixé sur une telle imprécision.** Élargir le jeu d'évaluation clinique est
donc un prérequis au go/no-go, avant toute autre optimisation du modèle.

## 4 bis. Jeu d'évaluation élargi — la mesure qui compte

### Dimensionnement

La taille n'a pas été choisie au jugé mais calculée, avant production, à partir
de la précision visée (`cas_necessaires`, `src/triage/training/statistiques.py`) :

| Précision visée | Urgences requises | Cas au total |
|---|---|---|
| ± 10 points *(situation antérieure)* | 43 | 129 |
| **± 5 points** | **169** | **~507** |
| ± 3 points | 467 | 1 401 |

**Cible retenue : 600 cas, soit 200 urgences maximales.**

Multiplier le volume sur six motifs n'aurait fait que répéter six tableaux. Huit
motifs de recours ont donc été ajoutés — colique néphrétique, douleur du mollet,
hypoglycémie, douleur pelvienne, épistaxis, agitation, rétention urinaire,
éruption fébrile — portant les **motifs réservés de 6 à 14**, toujours sans
aucun recouvrement avec l'entraînement (propriété verrouillée par test).

Composition obtenue : 600 cas, **200 par niveau**, 355 fr / 245 en, les 14
motifs représentés.

> **Défaut corrigé au passage.** Le script d'évaluation forçait 120 cas par une
> valeur codée en dur qui masquait la constante prévue à cet effet. Le premier
> run « élargi » a donc mesuré 120 cas sans le signaler. C'est exactement le
> type de panne silencieuse que le reste du projet cherche à rendre impossible ;
> la constante fait désormais foi.

### Résultats sur 600 cas

| | SFT | SFT + DPO (ablation) |
|---|---|---|
| Exactitude | 89,50 % **[86,79 – 91,71]** | 90,17 % **[87,52 – 92,30]** |
| Sous-triage global | 5,83 % | 5,67 % |
| Sur-triage | 4,67 % | 4,17 % |
| Sans niveau exploitable | 0,00 % | 0,00 % |
| **Sous-triage critique** | **8,50 %** [5,37 – 13,19] — 17/200 | **8,50 %** [5,37 – 13,19] — 17/200 |

Comparaison appariée sur les 600 mêmes cas : 5 cas gagnés par le SFT, 9 par le
modèle aligné, **p = 0,42**. L'écart n'est toujours pas significatif, mais il
est désormais mesuré avec une précision qui permet de le dire.

### Ce que le petit échantillon cachait

| | 40 urgences | 200 urgences |
|---|---|---|
| Sous-triage critique apparent | **2,5 %** | **8,5 %** |
| Intervalle de confiance | [0,4 % – 12,9 %] | [5,4 % – 13,2 %] |

Le premier chiffre n'était pas faux — il était imprécis. La vraie valeur était
dans son intervalle depuis le début ; c'est l'intervalle qui était trop large
pour qu'on puisse en tirer quoi que ce soit. **Un seuil d'acceptation fixé sur
les 120 cas aurait été fixé sur du bruit.**

C'est l'argument le plus solide du projet en faveur de la mesure d'incertitude :
sans elle, on aurait déployé en croyant à 2,5 % de sous-triage critique.

### Conséquence pour le service

Un sous-triage critique de 8,5 % signifie que **17 urgences vitales sur 200
seraient classées en priorité moindre** par le modèle servi seul. Aucun service
d'urgences ne l'accepterait.

C'est ce qui a dicté l'architecture de la semaine 4 : le modèle est **doublé
d'un barème explicite** qui relève la priorité quand le modèle annonce moins
grave que les constantes ne le justifient (cf. `docs/05-etape-3-deploiement.md`).

## 5. Modèle retenu et attribution des gains

Le livrable est le modèle **SFT + DPO (variante ablation)**, conforme au
cahier des charges. L'attribution des gains doit toutefois être énoncée
clairement :

- la **capacité de triage vient du SFT** — le modèle de base ne produit aucun
  niveau exploitable, le SFT atteint 91,92 % sans manquer une urgence ;
- la **contribution du DPO porte sur la qualité rédactionnelle**, pas sur la
  décision clinique : son effet sur le triage est positif sur le jeu de test,
  légèrement négatif hors distribution, et non significatif dans les deux cas.

### Enseignement méthodologique

Le triage possède une **vérité terrain déterministe** : le niveau se déduit de
règles vérifiables. Le DPO est conçu pour les tâches où la qualité est
subjective. Lui confier une décision calculable revient à substituer une
préférence relative à une réponse juste — les runs 1 et 2 en donnent la mesure.
Appliqué à ce pour quoi il est fait, il apporte un gain net.

Corollaire, valable au-delà de ce projet : **les métriques d'alignement mesurent
l'alignement, pas la qualité clinique**. Le run 1 affichait 87 % de paires bien
départagées tout en classant 95 % des prises en charge différées en urgence.
Seule l'évaluation sur cas réels l'a montré.
