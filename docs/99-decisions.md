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

| 2026-08-26 | Suivi d'expériences : **MLflow en local** (SQLite) | Le projet repose sur un discours de confidentialité ; envoyer les logs chez un tiers serait incohérent. MLflow 3 ayant déprécié le stockage fichier, le backend est `sqlite:///mlflow.db` |
| 2026-08-26 | Vérificateur de types : **ty** | Cohérent avec ruff, rapide ; ajouté comme étape bloquante de la CI |
| 2026-08-26 | `max_length = 1024` | Mesuré : p99 à 988 tokens, 0,66 % d'exemples tronqués ; 1 536 ne récupérerait que 0,64 % de plus pour 50 % d'activations en sus |
| 2026-08-26 | Lot de 2 × accumulation 8 | Le lot de 4 tient en VRAM (6,26 Go contre 5,99) mais ne change pas le débit : l'entraînement est limité par le calcul |
| 2026-08-26 | Accès par dictionnaire plutôt que `itertuples` | Les attributs d'un namedtuple pandas sont construits à l'exécution, donc invérifiables statiquement |

| 2026-08-26 | Fenêtre d'entraînement à **1 024 tokens** | Mesuré : p99 à 988, 0,66 % d'exemples tronqués ; 1 536 n'en récupérerait que 0,64 % de plus |
| 2026-08-26 | SFT : lot 2 × accumulation 8 ; DPO : lot 1 × accumulation 16 | Le DPO concatène les deux branches, un lot de 2 y produit 2,2 Go de logits |
| 2026-08-26 | `PYTORCH_CUDA_ALLOC_CONF=expandable_segments` pour le DPO | Les paires ont des longueurs très variables, ce qui fragmente le tas CUDA |
| 2026-08-26 | Six **motifs de recours réservés à l'évaluation** | Le jeu de test réutilise les motifs d'entraînement ; sans motifs inédits on mesure la mémorisation des gabarits |
| 2026-08-26 | **Taux de sous-triage critique** comme métrique de premier rang | L'exactitude globale masque le mode de défaillance dangereux : 91,9 % → 87,5 % pendant que les urgences manquées passent de 0 % à 12,5 % |
| 2026-08-26 | **Les paires de triage sont exclues de l'alignement** | Le triage a une vérité terrain déterministe, à laquelle le DPO ne convient pas. L'ablation le démontre : 64,65 % avec, 92,93 % sans |
| 2026-08-26 | Modèle livré : **SFT + DPO sur les seules paires UltraMedical** | Conforme au cahier des charges, et seule variante qui préserve la sécurité (31/31 urgences identifiées) |

| 2026-09-03 | Jeu de généralisation porté à **600 cas / 200 urgences**, motifs réservés de 6 à **14** | Dimensionné par calcul, pas au jugé : ±5 points de précision demandent 169 urgences. Augmenter le seul volume aurait répété six tableaux quatorze fois |
| 2026-09-03 | Hébergement : **Modal**, plan gratuit | Seule offre gratuite donnant un vrai GPU, donc la seule où vLLM garde un sens et où les latences sont défendables. 30 $ de crédits mensuels renouvelés, sans carte bancaire |
| 2026-09-03 | Un **seul conteneur GPU** : vLLM en sous-processus, API sur la boucle locale | Deux conteneurs doubleraient le démarrage à froid et feraient transiter chaque requête par le réseau sans contrepartie |
| 2026-09-03 | **Garde-fou par barème** : la priorité est relevée quand le modèle annonce moins grave | 8,5 % de sous-triage critique mesuré sur 200 urgences. Servir le modèle nu serait indéfendable ; le garde-fou n'agit que dans le sens de la sécurité |
| 2026-09-03 | **Règle d'arrêt du questionnaire déterministe**, jamais confiée au modèle | Un modèle décidant lui-même d'en savoir assez pourrait conclure sur un dossier vide : la panne la plus dangereuse du système |
| 2026-09-03 | **Prompt factorisé** entre génération de données et service | Un écart de mise en forme suffirait à faire chuter le modèle sans alerte, rendant caducs les scores mesurés. Vérifié : 1000 instructions régénérées à l'octet près |
| 2026-09-03 | Journal d'audit **chaîné par empreintes** | Un journal médical réécrivable ne prouve rien. Le chaînage rend l'altération visible — pas impossible, ce qui serait un autre problème |
| 2026-09-03 | Repli par barème **jamais silencieux** | Un service répondant avec le barème en croyant interroger le modèle fausserait toutes les mesures sans que rien ne le signale |
| 2026-09-03 | Poids publiés : **l'adaptateur seul** (67 Mo), pas le modèle fusionné | Republier 3,4 Go redistribuerait à l'identique des poids Qwen publics. vLLM charge l'adaptateur à chaud, ce qui permet le retour arrière sans reconstruire d'image |
| 2026-09-03 | CI : le job de qualité installe **tous les groupes** | Ce que le vérificateur de types ne peut pas importer, il ne vérifie pas. Un groupe oublié fait échapper un module au contrôle sans que rien ne le signale |
| 2026-09-03 | GPU : **A10G** et non T4 | Mesuré : 2 051 ms de médiane contre 8 046 ms, et 2 675 ms de p95 sous charge contre 23 040 ms. Le T4 ne gère ni bfloat16 ni FlashAttention 2, et sa bande passante mémoire est 2,4 fois inférieure |
| 2026-09-03 | Le modèle de base et le modèle affiné portent des **noms distincts** dans vLLM | S'ils partageaient une étiquette, un adaptateur manquant ferait servir le modèle nu sous le nom du modèle affiné : réponses plausibles et fausses, qu'aucune sonde ne détecte |
| 2026-09-03 | Le service **refuse de démarrer** sans adaptateur, et la configuration lue au déploiement est figée dans l'image | Une variable lue au niveau module n'existe pas dans le conteneur, qui réévalue le module à son démarrage. C'est exactement ce qui a fait servir le modèle nu au premier déploiement |
| 2026-09-03 | Publication : `ref/` et `training_args.bin` exclus du dépôt Hub | `ref/` est l'adaptateur de référence du DPO et doublait la taille ; télécharger un pickle depuis un dépôt public revient à exécuter du code qu'on n'a pas lu |

## À trancher

| Sujet | Options | Statut |
|---|---|---|
| ~~Hébergement de l'endpoint~~ | Modal, plan gratuit | ✅ tranché |
| ~~Volume du jeu DPO~~ | 3 000 paires produites, dont 2 000 servent à l'alignement | ✅ tranché |
| ~~Publication des poids~~ | HF Hub, adaptateur seul (67 Mo) | ✅ tranché — nécessite un jeton d'écriture |
| ~~Élargissement du jeu d'évaluation clinique~~ | 600 cas / 200 urgences | ✅ tranché |
| Hébergement du dataset | HF Hub (public/privé) / repo git + LFS | ⏳ |
| **Seuil d'acceptation du sous-triage critique** | à fixer par un clinicien, pas par l'équipe technique | ⏳ **bloque le go/no-go** |

