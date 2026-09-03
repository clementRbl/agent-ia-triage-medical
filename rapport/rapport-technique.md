<div class="titre">
<div class="surtitre">Centre Hospitalier Saint-Aurélien — Direction Innovation Médicale</div>

# Agent d'aide au triage aux urgences

<div class="sous-titre">Preuve de concept — rapport technique et recommandations stratégiques</div>

<div class="signature">
<strong>Clément Reboul</strong> — IA Engineer<br>
Mission de 4 semaines · Septembre 2026<br>
Commanditaire : D<sup>r</sup> Marie Dubois, Directrice Innovation Médicale
</div>

<div class="avertissement">
<strong>Ce système n'est pas un dispositif médical.</strong> Il ne pose pas de
diagnostic, ne prescrit pas et ne remplace aucune décision soignante. Le
barème employé est une transposition simplifiée de l'échelle FRENCH,
<strong>non validée par un clinicien</strong>. Toute mise en service suppose
une validation médicale préalable et une supervision permanente.
</div>
</div>

<div class="sommaire">

## Sommaire {.sans-saut}

1. Synthèse et recommandation
2. Contexte, périmètre et contraintes
3. Préparation des données
4. Spécialisation du modèle (SFT + LoRA)
5. Alignement par préférences (DPO)
6. Évaluation clinique
7. Architecture du service
8. Performances mesurées
9. Limites assumées
10. Passage à l'échelle — feuille de route
11. Conclusion : go / no-go

</div>

## 1. Synthèse et recommandation {.sans-saut}

Le POC démontre qu'un modèle compact de 1,7 milliard de paramètres, spécialisé
sur un corpus médical bilingue, apprend à évaluer un niveau de priorité de
triage à partir de constantes vitales — et non à reconnaître des gabarits
mémorisés. Sur des motifs de recours **jamais vus à l'entraînement**, il
classe correctement 90,2 % des cas, là où le modèle de base ne produit aucune
réponse exploitable.

Mais l'exactitude n'est pas la métrique qui décide. Sur 200 urgences vitales
évaluées, **17 sont annoncées à un niveau de priorité moindre**, soit un taux
de sous-triage critique de 8,5 % (intervalle de confiance à 95 % :
[5,4 % ; 13,2 %]).

<div class="chiffre-cle">
<strong>Recommandation.</strong> Le modèle ne peut pas être servi seul. Le
service livré le double d'un barème explicite qui relève la priorité lorsque
le modèle annonce moins grave que les constantes ne le justifient. Sous cette
condition, le POC est déployable <strong>en assistance et sous supervision
soignante</strong>, jamais en décision autonome. Le seuil d'acceptation du
taux de sous-triage critique doit être fixé par un clinicien, pas par l'équipe
technique.
</div>

Cette conclusion n'aurait pas pu être formulée avec le dispositif d'évaluation
initial. Sur 40 urgences, le taux apparent était de 2,5 % et son intervalle de
confiance s'étendait de 0,4 % à 12,9 % : aucun seuil n'y était fixable. C'est
en portant le jeu d'évaluation à 200 urgences que le chiffre réel est apparu.
**Le principal apport méthodologique de cette mission est là** : sans mesure
d'incertitude, le POC aurait été présenté comme trois fois plus sûr qu'il ne
l'est.

### Livrables

| Livrable | État |
| --- | --- |
| L1 — Dataset bilingue anonymisé, 5 000 paires SFT + 3 000 paires DPO | livré |
| L2 — Modèle Qwen3-1.7B spécialisé SFT + LoRA puis aligné DPO | livré |
| L3 — Endpoint de démonstration servi par vLLM | livré |
| L4 — Pipeline CI/CD GitHub Actions, tests et déploiement | livré |
| L5 — Rapport technique et recommandations | ce document |

## 2. Contexte, périmètre et contraintes

### Le besoin

Le service d'urgences du CHSA est en surcharge constante. L'agent doit
assister le personnel dans le tri initial : recueillir les symptômes, évaluer
un niveau de priorité parmi trois — **urgence maximale**, **modérée**,
**différée** —, expliquer son évaluation, s'intégrer au système d'information
hospitalier et garantir la traçabilité de chaque interaction.

### Le barème

Les trois niveaux demandés sont une transposition de l'échelle de tri
française **FRENCH**, qui en compte cinq :

| Niveau CHSA | Correspondance FRENCH | Délai de prise en charge |
| --- | --- | --- |
| Urgence maximale | tri 1–2 | immédiate ou < 20 min |
| Urgence modérée | tri 3 | < 60 min |
| Prise en charge différée | tri 4–5 | différée, réorientation possible |

Les critères de bascule retenus sont explicites et vérifiables : score de
Glasgow < 14, SpO₂ < 90 %, fréquence respiratoire > 30 ou < 8/min, pression
systolique < 90 mmHg, fréquence cardiaque > 130 ou < 40/min, ou présence d'un
signe de gravité. Ils placent le cas en urgence maximale. Un second jeu de
critères, moins sévères, définit l'urgence modérée.

> **Cette transposition n'a pas été validée par un clinicien.** C'est la
> limite structurante du POC : tout ce qui suit mesure la conformité du modèle
> à un barème, pas sa pertinence clinique.

### Les contraintes

| Contrainte | Conséquence |
| --- | --- |
| Modèle imposé : Qwen3-1.7B-Base | pas de comparaison avec un modèle plus grand |
| Matériel : RTX 3080, 10 Go partagés | LoRA obligatoire, lots réduits, mesures de VRAM préalables |
| Budget : nul | hébergement sur un plan gratuit à vrai GPU |
| Durée : 4 semaines | une seule campagne d'entraînement par étape |

## 3. Préparation des données

### Les sources ne sont pas celles prévues

Le cahier des charges désignait quatre corpus : MediQA, FrenchMedMCQA,
MedQuAD, UltraMedical-Preference. **Trois n'étaient plus accessibles** au
démarrage de la mission. Deux sources les remplacent :

| Source | Licence | Langue | Rôle |
| --- | --- | --- | --- |
| MediQAl | CC-BY-4.0 | français | raisonnement clinique, connaissance médicale |
| UltraMedical-Preference | MIT | anglais | socle anglophone, paires de préférence |

Vérification faite, **MedQuAD et MedQA sont des sous-sources d'UltraMedical** :
les corpus demandés sont, pour partie, effectivement présents dans le jeu
produit.

### Aucun corpus de triage n'existe

C'est le constat déterminant de la semaine 1, et il a été mesuré, pas supposé :
sur les cas cliniques de MediQAl, **3 % seulement portent des constantes
vitales structurées**, **aucun ne porte de niveau de priorité**, et les
questions relevant de l'urgence représentent 5,3 % du corpus.

Sans niveau de priorité, le champ central du schéma reste vide et le taux de
sous-triage — la métrique de sécurité du projet — est tout simplement
impossible à calculer.

D'où un quatrième bloc de **cas de triage construits par règles explicites** :
les constantes sont tirées dans des bornes physiologiques, puis le niveau de
priorité en est **déduit** par les critères du barème. Le label n'est jamais
choisi : il est la conséquence vérifiable du tableau clinique. Une règle fausse
devient alors un bug détectable par un test, au lieu d'une erreur diffuse dans
mille exemples.

### Composition du jeu SFT — 5 000 paires

| Bloc | Volume | Langue | Contenu |
| --- | --- | --- | --- |
| A — raisonnement clinique | 2 000 | fr | cas cliniques MediQAl |
| B — connaissance médicale | 1 000 | fr | questions de connaissance MediQAl |
| C — socle anglophone | 1 000 | en | UltraMedical |
| D — triage structuré | 1 000 | 637 fr / 363 en | cas construits par règles |

Découpage : 3 986 entraînement / 488 validation / 526 test.

### Composition du jeu DPO — 3 000 paires

| Type | Volume | Origine |
| --- | --- | --- |
| Préférences difficiles | 1 323 | UltraMedical |
| Préférences faciles | 677 | UltraMedical |
| Sous-triage rejeté | 501 | construites |
| Sur-triage rejeté | 499 | construites |

Les paires étiquetées `length` sont exclues : le biais de longueur est un
artefact connu de ce corpus et fausserait l'alignement.

### Anonymisation et conformité RGPD

Chaîne Presidio bilingue (`fr_core_news_md`, `en_core_web_md`), enrichie de
reconnaisseurs propres au contexte français : numéro de sécurité sociale,
civilité suivie du patronyme, dates absolues, établissements de santé.
Remplacement par marqueurs typés — `<PATIENT>`, `<DATE>`, `<NIR>`.

**Le masquage générique dégradait le corpus.** Presidio identifiait comme
personnes des éponymes et des termes de biologie : *Parkinson* (10
occurrences), *Babinski* (8), *Senning* (8), mais aussi *Hémoglobine*,
*Créatinine*, *Cyanose*. Masquer ces termes aurait supprimé le signal clinique
même que le modèle doit apprendre.

Un filtre à quatre règles a été ajouté : casse initiale des patronymes
français, exclusion des jetons d'une lettre, lexique médical de référence,
contexte éponymique (*maladie de*, *signe de*, *indice de*).

| | Avant filtrage | Après filtrage |
| --- | --- | --- |
| Détections PERSON | 892 | 534 |
| PII résiduelle mesurée | 1,19 % | **0,20 %** |

Deux catégories sont **délibérément préservées** : les lieux et les durées. Un
« séjour au Gabon » conditionne une prophylaxie antipaludique, une douleur
« depuis 30 minutes » ne se traite pas comme une douleur « depuis 5 jours ».
Les masquer produirait un corpus conforme et cliniquement inutile. Les âges de
90 ans et plus sont en revanche généralisés en « 90+ », l'âge extrême étant un
quasi-identifiant.

Un contrôle a révélé une fuite réelle : « Monsieur V. Joseph » n'était masqué
qu'en « Monsieur V. », laissant « Joseph » en clair. L'expression régulière
capture désormais jusqu'à trois jetons patronymiques ; un test de
non-régression verrouille le cas.

### Absence de fuite entre les jeux

Plusieurs questions partagent un même cas clinique : un découpage ligne à
ligne ferait apparaître le même cas des deux côtés de la frontière. Le
découpage se fait donc **par groupe**, sur l'empreinte SHA-256 de la clé de
cas — affectation déterministe et stable quand le corpus grandit. Les
identifiants UltraMedical sont partitionnés en trois viviers disjoints
(SFT 35 %, DPO 50 %, évaluation 15 %).

**Recouvrement mesuré entre entraînement et évaluation : zéro.** La propriété
est vérifiée à chaque exécution de la chaîne d'intégration.

### Traçabilité

Chaque étape de transformation écrit un **manifeste d'audit** : empreinte
SHA-256 du fichier produit, nombre de lignes, paramètres, statistiques,
horodatage et révision du dépôt. Les manifestes sont versionnés et contrôlés
en intégration continue.

## 4. Spécialisation du modèle (SFT + LoRA)

### Configuration

| | |
| --- | --- |
| Modèle de base | `Qwen/Qwen3-1.7B-Base` |
| Méthode | LoRA, r = 16, α = 32, dropout 0,05, 7 projections par bloc |
| Paramètres entraînés | 17,4 M sur 1,74 Md — **1,00 %** |
| Lot effectif | 16 (lot 2 × accumulation 8) |
| Fenêtre | 1 024 tokens |
| Optimisation | lr 2 · 10⁻⁴, ordonnancement cosinus, bf16 |
| Graine | 42 |
| Durée | **41 min 33 s** — 500 pas, 2 époques |
| VRAM au pic | **5,99 Go** sur 10 Go |
| Adaptateur produit | **67 Mo** |

### Dimensionné par la mesure, pas par convention

Chaque valeur ci-dessus a été choisie après mesure sur le corpus réel :

- **Fenêtre de 1 024 tokens.** Distribution mesurée : médiane 332 tokens, p99 à
  988. À 1 024, 0,66 % des exemples sont tronqués ; passer à 1 536 n'en
  récupérerait que 0,64 % de plus, pour 50 % d'activations supplémentaires.
- **VRAM.** Sonde préalable sur les 32 exemples les plus longs : pic à 5,99 Go,
  4,35 Go de marge. Aucun dépassement en cours d'entraînement.
- **Taille de lot.** Un lot de 4 tient en mémoire (6,26 Go) mais **ne change pas
  le débit** : l'entraînement est limité par le calcul, pas par les lancements
  de noyaux. Le lot de 2 est conservé pour la marge.

### Convergence

| Pas | 50 | 100 | 200 | 300 | 400 | 450 | 500 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Perte de validation | 1,5385 | 1,4516 | 1,3899 | 1,3685 | 1,3579 | 1,3587 | 1,3576 |

La perte plafonne dès le pas 400, soit 1,6 époque ; les cent derniers pas
gagnent 0,0003. **Aucune remontée : pas de sur-apprentissage**, ce qui répond
au point de vigilance du cahier des charges. Pour un run ultérieur, 1,6 époque
suffirait et économiserait huit minutes.

### Résultat sur le jeu de test

99 cas de triage jamais vus (42 différés, 31 maximales, 26 modérées ;
54 fr / 45 en), génération déterministe.

| | Modèle de base | Après SFT |
| --- | --- | --- |
| Exactitude | 0 % | **91,92 %** |
| Sous-triage | — | 4,04 % |
| Sur-triage | — | 4,04 % |
| Urgences vitales identifiées | 0 / 31 | **31 / 31** |

Le modèle de base ne produit **aucun niveau exploitable** : l'apport du SFT
n'est pas une amélioration marginale, c'est le passage d'inutilisable à
exploitable.

## 5. Alignement par préférences (DPO)

Trois campagnes ont été nécessaires. Les deux échecs sont rapportés ici parce
qu'ils sont plus instructifs que le succès.

### Run 1 — préférences unidirectionnelles

Toutes les paires de triage rejetaient une réponse **minorant** la priorité,
dans l'intention de combattre le sous-triage.

| | Après SFT | Après DPO run 1 |
| --- | --- | --- |
| Exactitude | 91,92 % | **42,42 %** |
| Sur-triage | 4,04 % | **57,58 %** |

Le modèle classait 95 % des prises en charge différées en urgence. La cause
est structurelle : sous une distribution où la réponse plus basse est
*toujours* la mauvaise, la politique optimale consiste à annoncer toujours le
niveau le plus haut. Les cas déjà différés étaient de surcroît exclus du jeu,
supprimant le dernier contre-exemple possible.

### Run 2 — préférences bidirectionnelles

Les paires ont été rééquilibrées : rejet du sous-triage pour les urgences,
rejet du sur-triage pour les cas différés. Résultat : 64,65 % d'exactitude,
**13 urgences vitales manquées sur 31**.

Les réponses `chosen` et `rejected` partagent environ 90 % de leurs jetons —
seul le niveau annoncé et le critère cité diffèrent. Le gradient se concentre
donc sur ces quelques jetons, et le modèle a appris à permuter le **libellé du
critère** en même temps que le niveau, produisant des justifications
incohérentes avec les constantes affichées :

```
Constantes : FR 5/min   (critère réel : « FR > 30/min ou < 8/min »)
SFT   URGENCE MAXIMALE · fréquence respiratoire > 30/min ou < 8/min (FR 5/min)
DPO   URGENCE MODÉRÉE  · fréquence respiratoire entre 25 et 30/min (FR 5/min)
```

Second dégât : une **contamination linguistique**, des fragments anglais
apparaissant dans les réponses françaises, les deux tiers des paires de
préférence étant anglophones.

### Run 3 — ablation

DPO sur les seules paires UltraMedical, **sans aucune paire de triage**.
Objectif : distinguer l'effet des paires de triage de celui des données
anglophones.

| | Base | SFT | DPO run 1 | DPO run 2 | **DPO ablation** |
| --- | --- | --- | --- | --- | --- |
| Exactitude | 0 % | 91,92 % | 42,42 % | 64,65 % | **92,93 %** |
| Sous-triage | — | 4,04 % | 0 % | 14,14 % | 4,04 % |
| Sur-triage | — | 4,04 % | 57,58 % | 21,21 % | **3,03 %** |
| Urgences identifiées | 0/31 | 31/31 | 31/31 | 13/31 | **31/31** |

**Hypothèse confirmée** : les paires portant sur la décision de triage étaient
la cause des deux échecs, et non les données anglophones. La contamination
linguistique du run 2 provenait elle aussi de la dérive globale provoquée par
un signal contradictoire.

### Enseignement

Le triage possède une **vérité terrain déterministe** : le niveau se déduit de
règles vérifiables. Le DPO est conçu pour les tâches où la qualité est
subjective — ton, clarté, pertinence d'une explication. Lui confier une
décision calculable revient à substituer une préférence relative à une réponse
juste.

Corollaire, valable au-delà de ce projet : **les métriques d'alignement
mesurent l'alignement, pas la qualité clinique.** Le run 1 affichait 87 % de
paires correctement départagées tout en classant 95 % des prises en charge
différées en urgence. Seule l'évaluation sur cas cliniques l'a révélé.

Le modèle livré est donc **SFT + DPO sur les seules paires UltraMedical** :
conforme au cahier des charges, et seule variante qui préserve la propriété de
sécurité.
