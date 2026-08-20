# 05 — Étape 3 : Déployer et valider le POC

## Objectifs

- **Automatiser le déploiement** du prototype via le pipeline CI/CD
  **GitHub Actions**.
- **Conteneuriser** l'application avec **Docker** et l'exposer via une API
  **FastAPI**, en utilisant **vLLM** pour une inférence optimisée.
- Réaliser des **tests de latence**, de **robustesse**, et des **audits de
  traçabilité** des interactions.

## Prérequis

- Le modèle fine-tuné et validé est disponible.
- Le pipeline CI/CD GitHub est fonctionnel.

## Résultats attendus

1. Un **endpoint de démonstration déployé et accessible** en environnement pilote.
2. Un **processus de déploiement automatisé et reproductible**.
3. Le **rapport final** incluant les métriques de performance et la roadmap.

## Recommandations

- Mesurer la **latence et le temps de réponse en conditions réalistes**.
- Préparer un **plan de mise en production conditionnel** : checklist
  **« go / no-go »**.

## Points de vigilance

- ❗ Protéger les **clés / secrets** et l'accès aux endpoints.
- ❗ Prévoir des **procédures de surveillance après déploiement**.
- ❗ Documenter clairement les **limites d'usage** pour les utilisateurs.

## Outils

vLLM · Docker · FastAPI · GitHub Actions

## Architecture cible du POC

```
Client (curl / UI démo)
        │  HTTPS + clé d'API
        ▼
   FastAPI  ──────────────── logs d'audit horodatés (traçabilité)
        │  OpenAI-compatible
        ▼
   vLLM (Qwen3-1.7B + adaptateur LoRA DPO)
        │
        ▼
      GPU cloud
```

## Traçabilité des interactions (exigence client)

Chaque interaction doit être auditable :
- horodatage, identifiant de session, version du modèle/adaptateur ;
- entrée patient (anonymisée), sortie du modèle, niveau de priorité ;
- latence, nombre de tokens ;
- **jamais de PII en clair dans les logs** (règle projet + RGPD).

## Checklist go / no-go (à compléter en S4)

- [ ] Taux de sous-triage sous le seuil défini en S2
- [ ] Latence P95 sous le seuil défini
- [ ] Endpoint protégé par authentification
- [ ] Logs d'audit complets et sans PII
- [ ] Limites d'usage documentées et affichées
- [ ] Procédure de rollback testée
