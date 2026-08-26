# 00 — Contexte de la mission

## Client

**Centre Hospitalier Saint-Aurélien (CHSA)** — grand hôpital public français.
**Commanditaire :** Dr. Marie Dubois, Directrice Innovation Médicale.
**Rôle tenu :** IA Engineer junior.
**Durée :** 4 semaines.

## Problème métier

Le service des urgences du CHSA est en surcharge constante, en particulier aux
heures de pointe. Le personnel infirmier et de triage manque parfois d'effectifs,
ce qui entraîne :

- des temps d'attente prolongés ;
- un risque de non-identification rapide des cas critiques.

## Objet du projet

Réaliser un **POC (Proof of Concept)** d'agent IA de triage médical démontrant
la **faisabilité technique** et la **valeur ajoutée clinique** du système.

L'agent doit :

1. **Collecter** les symptômes via un questionnaire intelligent adaptatif.
2. **Évaluer** le niveau de priorité — *urgence maximale / modérée / différée* —
   selon les protocoles médicaux.
3. **Expliquer** clairement l'évaluation et les recommandations.
4. **S'intégrer** au système d'information hospitalier existant.
5. **Tracer** chaque interaction pour les audits médicaux.

## Stratégie en 3 phases (vision du client)

| Phase | Intitulé | Contenu | Périmètre POC |
|-------|----------|---------|---------------|
| 1 | Validation conceptuelle | Déploiement de **Qwen3-1.7B-Base** : valider vite les hypothèses techniques et l'acceptabilité clinique | ✅ réalisé |
| 2 | Optimisation ciblée | **SFT + LoRA**, puis alignement par préférences **DPO** sur protocoles médicaux | ✅ réalisé |
| 3 | Projection industrielle | Passage à des modèles 32B+, datasets étendus, architecture de données médicales soignée (symptomatologie, antécédents, constantes vitales, protocoles de triage) | ➡️ roadmap uniquement |

## Hypothèse de départ

Les LLM médicaux spécialisés atteignent des performances diagnostiques
comparables à celles de médecins en formation — sous réserve d'une méthodologie
rigoureuse et d'une validation approfondie avant tout déploiement clinique.

## Cadrage / limites à porter dans le rapport

- Le système est un **outil d'aide au triage**, pas un dispositif de diagnostic
  autonome. Décision finale = personnel soignant.
- Statut réglementaire (dispositif médical / MDR, AI Act) : hors périmètre du
  POC, à documenter comme point de vigilance dans la roadmap.
- Aucune donnée patient réelle n'est utilisée : corpus publics anonymisés.
- Le barème de triage est une transposition simplifiée de l'échelle FRENCH,
  **non validée par un clinicien**. Sa validation par le comité médical du CHSA
  est un prérequis à toute phase 2.
- Les performances mesurées portent sur des cas **construits**, pas sur des
  passages réels aux urgences. Elles démontrent la faisabilité technique, pas
  l'efficacité clinique.
