"""Fabrique l'archive de rendu a partir des livrables produits.

La plateforme attend une archive zip dont chaque entree porte le nom
`Nom_Prenom_<n>_<livrable>_<mmaaaa>`, ou `mmaaaa` designe le mois de
demarrage du projet -- pas la date de rendu. La convention est rappelee
dans docs/01-livrables.md.

Les cinq livrables ne vivent pas au meme endroit : le jeu de donnees et le
rapport sont dans le depot, l'adaptateur est un artefact d'entrainement, le
service et la chaine de livraison sont du code. Ce script les rassemble
plutot que de laisser l'assemblage se faire a la main, ou une erreur de
nommage passerait inapercue jusqu'au depot.

Usage :
    uv run python scripts/construire_archive.py
"""

from __future__ import annotations

import argparse
import shutil
import sys
import zipfile
from collections.abc import Iterator
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
DESTINATION = RACINE / "outputs" / "livrables"
ARCHIVE = "Agent_IA_Triage_Medical_Reboul_Clement.zip"
PREFIXE = "Reboul_Clement"
PERIODE = "082026"

MODELE_HF = "https://huggingface.co/ClementRbl/triage-chsa-qwen3-1.7b"
ENDPOINT = "https://clement-rbl--triage-chsa-service.modal.run"

# `ref` est l'adaptateur de reference du DPO : il sert a calculer la divergence
# pendant l'entrainement, n'a aucun usage pour qui recoit le livrable et pese
# autant que l'adaptateur utile. `__pycache__` est du cache d'interpreteur, qui
# n'a rien a faire dans un rendu.
EXCLUS = {"ref", "__pycache__"}


def _fichiers(racine: Path) -> Iterator[Path]:
    """Enumere les fichiers d'un dossier, sans les repertoires exclus."""
    for chemin in sorted(racine.rglob("*")):
        if chemin.is_file() and not EXCLUS & set(chemin.relative_to(racine).parts):
            yield chemin


def _ecrire_zip(cible: Path, sources: list[tuple[Path, str]], notes: dict[str, str]) -> int:
    """Ecrit un zip depuis des couples (fichier, nom dans l'archive)."""
    cible.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(cible, "w", zipfile.ZIP_DEFLATED) as zf:
        for chemin, nom in sources:
            zf.write(chemin, nom)
        for nom, contenu in notes.items():
            zf.writestr(nom, contenu)
    return cible.stat().st_size


def _dossier(racine: Path, prefixe: str) -> list[tuple[Path, str]]:
    return [(f, f"{prefixe}/{f.relative_to(racine).as_posix()}") for f in _fichiers(racine)]


NOTE_MODELE = f"""# Livrable 2 — Modele specialise

Adaptateurs LoRA de `Qwen3-1.7B-Base`, specialise par SFT puis aligne par DPO.
Ce sont les poids finaux : l'adaptateur, sa configuration, le tokenizer et le
gabarit de conversation.

Le modele de base n'est pas redistribue ici. Il se telecharge depuis son depot
d'origine (`Qwen/Qwen3-1.7B-Base`) et l'adaptateur se pose dessus.

Version publiee, avec sa carte de modele, ses metriques et ses limites d'usage :
{MODELE_HF}

## Charger l'adaptateur

```python
from peft import PeftModel
from transformers import AutoModelForCausalLM

base = AutoModelForCausalLM.from_pretrained("Qwen/Qwen3-1.7B-Base")
modele = PeftModel.from_pretrained(base, "adaptateur")
```

Le gabarit a ete entraine avec `enable_thinking=False` : servir avec un autre
reglage changerait la distribution des sorties.
"""

NOTE_ENDPOINT = f"""# Livrable 3 — Endpoint de demonstration

Service en ligne : {ENDPOINT}

| Adresse | Contenu |
|---|---|
| `/` | page de demonstration : le questionnaire adaptatif, deroule pas a pas |
| `/docs` | documentation interactive, avec exemples prets a envoyer |
| `/sante` | sonde de disponibilite, seule route non protegee |

L'acces est protege par l'en-tete `X-Cle-Api`. La cle est remise separement :
elle n'est pas dans cette archive, et n'a jamais ete dans le depot.

## Contenu

`deploiement/` rassemble le Dockerfile, le point d'entree du conteneur et la
description de la fonction distante, ainsi que la procedure complete de
deploiement et de rotation des secrets.

## Demarrage a froid

L'hebergement eteint le conteneur apres cinq minutes d'inactivite. Le premier
appel qui suit paie de deux a trois minutes et demie de remise en route.
Appeler `/sante` quelques minutes avant une demonstration evite l'attente.
"""

NOTE_CICD = """# Livrable 4 — Chaine d'integration et de livraison

Deux workflows GitHub Actions.

`ci.yml` s'execute sur chaque pull request et sur `main`, en trois travaux
paralleles :

| Travail | Controle |
|---|---|
| Lint, format et types | `ruff check`, `ruff format --check`, `ty check` sur tout le depot |
| Tests | plus de 200 tests unitaires |
| Integrite du jeu de donnees | empreintes des manifestes, PII residuelle, absence de fuite |

`deploiement.yml` se declenche quand la CI passe au vert sur `main`. Il
redeploie le service, puis mesure sur le service reellement deploye : latence
sequentielle et sous charge, robustesse aux saisies fautives, integrite de la
chaine d'audit. Les mesures sont conservees en artefact de build.

Le script de verification sort en erreur si un controle echoue : un deploiement
qui repond mal doit teindre la chaine en rouge, pas passer inapercu.
"""


def _livrables(depot: Path) -> list[tuple[str, Path, list[tuple[Path, str]], dict[str, str]]]:
    """Decrit les cinq livrables : nom, source a verifier, contenu, notes."""
    donnees = depot / "data" / "processed"
    adaptateur = depot / "outputs" / "dpo" / "adaptateur"
    deploiement = depot / "deploiement"
    workflows = depot / ".github" / "workflows"
    return [
        ("1_Dataset", donnees, _dossier(donnees, "jeu-de-donnees"), {}),
        ("2_Modele", adaptateur, _dossier(adaptateur, "adaptateur"), {"LISEZ-MOI.md": NOTE_MODELE}),
        (
            "3_Endpoint",
            deploiement,
            _dossier(deploiement, "deploiement"),
            {"LISEZ-MOI.md": NOTE_ENDPOINT},
        ),
        (
            "4_CICD",
            workflows,
            _dossier(workflows, "workflows"),
            {"LISEZ-MOI.md": NOTE_CICD},
        ),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=DESTINATION)
    args = parser.parse_args()

    rapport = RACINE / "rapport" / f"{PREFIXE}_5_Rapport_{PERIODE}.pdf"
    if not rapport.is_file():
        print(f"rapport absent : {rapport}", file=sys.stderr)
        print("fabriquez-le d'abord : uv run python scripts/construire_rapport.py", file=sys.stderr)
        return 1

    travail = args.destination / "contenu"
    if travail.exists():
        shutil.rmtree(travail)
    travail.mkdir(parents=True)

    entrees: list[Path] = []
    for suffixe, source, contenu, notes in _livrables(RACINE):
        if not source.is_dir():
            print(f"source absente pour le livrable {suffixe} : {source}", file=sys.stderr)
            return 1
        cible = travail / f"{PREFIXE}_{suffixe}_{PERIODE}.zip"
        taille = _ecrire_zip(cible, contenu, notes)
        print(f"  {cible.name:44s} {len(contenu):4d} fichiers  {taille / 1e6:7.1f} Mo")
        entrees.append(cible)

    copie = travail / rapport.name
    shutil.copy2(rapport, copie)
    print(f"  {copie.name:44s} {'':4s}            {copie.stat().st_size / 1e6:7.1f} Mo")
    entrees.append(copie)

    archive = args.destination / ARCHIVE
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_STORED) as zf:
        for entree in entrees:
            zf.write(entree, entree.name)

    print(f"\necrit : {archive.relative_to(RACINE)} — {archive.stat().st_size / 1e6:.1f} Mo")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
