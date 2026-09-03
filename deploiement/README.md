# Déploiement du service de triage

Trois cibles, un seul code de service : Modal pour la démonstration en ligne,
Docker pour reproduire le service ailleurs, et l'exécution locale pour
développer sans GPU.

## Pourquoi Modal

L'endpoint doit être servi par vLLM, donc sur GPU. Le plan gratuit de Modal
renouvelle 30 $ de crédits chaque mois **sans carte bancaire**, soit environ
187 heures de T4 — très au-delà de ce qu'une démonstration consomme. Les
offres gratuites concurrentes (Hugging Face Spaces, notamment) sont limitées
au CPU : vLLM y perdrait sa raison d'être et les mesures de latence tout leur
sens.

Le conteneur s'éteint après cinq minutes sans trafic. Le premier appel qui
suit paie un démarrage à froid de 27 s : c'est le prix du coût nul, et le
script de mesure le rapporte séparément plutôt que de le noyer dans la moyenne.

### Le GPU se choisit sur mesure

`TRIAGE_GPU` vaut `A10G` par défaut. Le T4, moins cher, a été mesuré puis
écarté :

| GPU | Médiane séquentielle | p95 sous charge |
| --- | --- | --- |
| T4 | 8 046 ms | 23 040 ms |
| **A10G** | **2 051 ms** | **2 675 ms** |

Le T4 ne gère ni bfloat16 ni FlashAttention 2, et sa bande passante mémoire est
2,4 fois inférieure. Une p95 à 23 secondes serait inutilisable à un guichet.

## Mise en service, une fois

### 1. Publier l'adaptateur

Les poids servis sont tirés du Hub au démarrage du conteneur. Créer un jeton
d'écriture sur <https://huggingface.co/settings/tokens>, puis :

```bash
export HF_TOKEN=hf_...
uv run python scripts/publier_modele.py --depot <compte>/triage-chsa-qwen3-1.7b
```

L'adaptateur pèse 67 Mo. Republier le modèle fusionné (3,4 Go) redistribuerait
à l'identique des poids Qwen déjà publics.

### 2. Créer le secret Modal

```bash
uv run modal secret create triage-secrets \
  TRIAGE_CLES_API="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
```

Ce secret protège l'endpoint. Sans clé configurée le service reste ouvert :
c'est le mode développement local, jamais un mode de production.

### 3. Déployer

```bash
export TRIAGE_ADAPTATEUR=<compte>/triage-chsa-qwen3-1.7b
uv run modal deploy deploiement/modal_app.py
```

Modal affiche l'URL du service. La conserver : elle alimente la variable de
dépôt `URL_SERVICE` utilisée par la chaîne d'intégration.

### 4. Vérifier

```bash
export TRIAGE_CLE_API=<la clé créée à l'étape 2>
uv run python scripts/mesurer_service.py --url https://<endpoint>
```

Le script mesure la latence (démarrage à froid, séquentielle, sous charge),
éprouve la robustesse aux saisies fautives et vérifie l'intégrité du journal
d'audit. Il sort en erreur si un contrôle échoue.

## Déploiement automatique

`.github/workflows/deploiement.yml` redéploie à chaque passage vert de la CI
sur `main`. À renseigner dans **Settings → Secrets and variables → Actions** :

| Nom | Type | Rôle |
| --- | --- | --- |
| `MODAL_TOKEN_ID` | secret | jeton Modal (`modal token new`) |
| `MODAL_TOKEN_SECRET` | secret | jeton Modal |
| `TRIAGE_CLE_API` | secret | clé d'appel, pour la vérification |
| `TRIAGE_ADAPTATEUR` | variable | dépôt Hub de l'adaptateur |
| `TRIAGE_MODELE_BASE` | variable | modèle de base (défaut : `Qwen/Qwen3-1.7B-Base`) |
| `URL_SERVICE` | variable | URL renvoyée par Modal |

Aucun secret n'entre dans l'image ni dans le dépôt : ils sont injectés à
l'exécution.

**Rotation.** Pour remplacer la clé d'appel :

```bash
nouvelle=$(python -c 'import secrets; print(secrets.token_urlsafe(32))')
uv run modal secret create triage-secrets TRIAGE_CLES_API="$nouvelle" --force
gh secret set TRIAGE_CLE_API --body "$nouvelle"
uv run modal deploy deploiement/modal_app.py
```

Les jetons Modal se régénèrent depuis <https://modal.com/settings/tokens>, le
jeton Hugging Face depuis <https://huggingface.co/settings/tokens>.

Tant que `MODAL_TOKEN_ID` et `MODAL_TOKEN_SECRET` ne sont pas renseignés, le
workflow **s'arrête avec un avertissement plutôt qu'en échec** : rien n'est
cassé, et une chaîne durablement rouge finirait par rendre un vrai échec
invisible. Une fois les secrets posés, tout échec devient bloquant.

## Docker

```bash
docker build -f deploiement/Dockerfile -t triage-chsa .
docker run --gpus all -p 8080:8080 \
  -e ADAPTATEUR=<compte>/triage-chsa-qwen3-1.7b \
  -e TRIAGE_CLES_API=<clé> \
  -v triage-journal:/journal \
  triage-chsa
```

Le volume `/journal` est indispensable : sans lui, chaque redémarrage
effacerait les traces médicales.

## Local, sans GPU

Le moteur de repli déduit la réponse du seul barème. Il sert à développer
l'API et à la tester en intégration continue, jamais à produire une mesure.

```bash
TRIAGE_MOTEUR=regles uv run uvicorn triage.api.app:app --reload --port 8080
```

Documentation interactive sur <http://127.0.0.1:8080/docs>.

## Points d'entrée

| Route | Rôle |
| --- | --- |
| `GET /sante` | sonde de vivacité, non protégée |
| `GET /version` | version du service, moteur et modèle servis |
| `POST /entretiens` | ouvre un entretien, renvoie la première question |
| `POST /entretiens/{session}/reponses` | répond, obtient la suite ou le triage |
| `POST /triage` | trie un dossier complet en une passe (intégration SIH) |
| `GET /audit/{session}` | déroulé complet d'un entretien |
| `GET /audit` | vérifie l'intégrité du journal |

Toutes les routes sauf `/sante` exigent l'en-tête `X-Cle-Api`.
