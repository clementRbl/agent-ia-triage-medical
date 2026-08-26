"""Generation et evaluation d'un modele sur les cas de triage du jeu de test.

Sert a comparer trois etats du modele -- base, apres SFT, apres DPO -- sur
exactement les memes cas, tires du split de test qui n'a jamais servi a
l'entrainement.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from triage.schema import NiveauPriorite
from triage.training.config import MODELE_BASE
from triage.training.evaluation import ResultatEvaluation, comparer, extraire_niveau

TRAITE = Path("data/processed")


def charger_modele(adaptateur: Path | None = None, modele: str = MODELE_BASE) -> tuple[Any, Any]:
    """Charge le modele de base, eventuellement coiffe d'un adaptateur LoRA."""
    tokenizer = AutoTokenizer.from_pretrained(str(adaptateur) if adaptateur else modele)
    if tokenizer is None:
        raise RuntimeError(f"Tokenizer introuvable pour {adaptateur or modele}")
    # Padding a gauche : sur un modele causal, un padding a droite decalerait
    # la position de generation et produirait des sorties tronquees.
    tokenizer.padding_side = "left"
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    reseau = AutoModelForCausalLM.from_pretrained(
        modele,
        dtype=torch.bfloat16,
        device_map={"": 0} if torch.cuda.is_available() else None,
    )
    if adaptateur is not None:
        from peft import PeftModel

        reseau = PeftModel.from_pretrained(reseau, str(adaptateur))
        reseau = reseau.merge_and_unload()  # fusionne : inference plus rapide
    reseau.eval()
    return reseau, tokenizer


@torch.no_grad()
def generer(
    reseau: Any,
    tokenizer: Any,
    instructions: list[str],
    tokens_max: int = 320,
    taille_lot: int = 8,
) -> list[str]:
    """Genere une reponse par instruction, en mode deterministe.

    Pas d'echantillonnage : une evaluation doit etre reproductible, et deux
    executations du meme modele doivent donner le meme taux de sous-triage.
    """
    sorties: list[str] = []
    for debut in range(0, len(instructions), taille_lot):
        lot = instructions[debut : debut + taille_lot]
        invites = [
            tokenizer.apply_chat_template(
                [{"role": "user", "content": texte}],
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=False,
            )
            for texte in lot
        ]
        entrees = tokenizer(invites, return_tensors="pt", padding=True, truncation=True).to(
            reseau.device
        )
        produits = reseau.generate(
            **entrees,
            max_new_tokens=tokens_max,
            do_sample=False,
            pad_token_id=tokenizer.pad_token_id,
        )
        for sequence in produits:
            # On ne garde que ce qui a ete genere apres l'invite.
            nouveaux = sequence[entrees["input_ids"].shape[1] :]
            sorties.append(tokenizer.decode(nouveaux, skip_special_tokens=True))
    return sorties


def cas_de_triage(split: str = "test", dossier: Path = TRAITE) -> pd.DataFrame:
    """Cas de triage du split demande, seuls porteurs d'un niveau de reference."""
    donnees = pd.read_parquet(dossier / "sft.parquet")
    return donnees[
        (donnees["split"] == split) & (donnees["bloc"] == "D_triage_structure")
    ].reset_index(drop=True)


def _evaluer(
    nom: str,
    instructions: list[str],
    attendus: list[NiveauPriorite],
    adaptateur: Path | None,
    tokens_max: int,
) -> tuple[ResultatEvaluation, list[str]]:
    reseau, tokenizer = charger_modele(adaptateur)
    reponses = generer(reseau, tokenizer, instructions, tokens_max=tokens_max)
    predits = [extraire_niveau(r) for r in reponses]

    del reseau
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    return comparer(attendus, predits, nom, instructions=instructions), reponses


def evaluer_modele(
    nom: str,
    adaptateur: Path | None = None,
    split: str = "test",
    limite: int | None = None,
    tokens_max: int = 320,
) -> tuple[ResultatEvaluation, list[str]]:
    """Evalue sur les cas de triage du jeu, batis sur les motifs d'entrainement."""
    cas = cas_de_triage(split)
    if limite:
        cas = cas.head(limite)
    if cas.empty:
        raise ValueError(f"Aucun cas de triage dans le split {split!r}")
    return _evaluer(
        nom,
        cas["instruction"].tolist(),
        [NiveauPriorite(v) for v in cas["niveau_priorite"]],
        adaptateur,
        tokens_max,
    )


def evaluer_generalisation(
    nom: str,
    adaptateur: Path | None = None,
    nombre: int = 120,
    graine: int = 777,
    tokens_max: int = 320,
) -> tuple[ResultatEvaluation, list[str]]:
    """Evalue sur des motifs de recours **jamais vus a l'entrainement**.

    Le jeu de test ordinaire reutilise les douze motifs d'entrainement : un
    modele peut y exceller en retenant la forme des cas. Ici les six motifs
    sont inedits, ce qui distingue l'apprentissage de la regle de triage de la
    simple memorisation des gabarits.
    """
    from triage.data.triage import PRESENTATIONS_INEDITES, generer_cas

    cas = generer_cas(
        nombre,
        graine=graine,
        presentations=PRESENTATIONS_INEDITES,
        prefixe="generalisation",
    )
    attendus = [c.niveau_priorite for c in cas if c.niveau_priorite is not None]
    instructions = [c.instruction for c in cas if c.niveau_priorite is not None]
    return _evaluer(nom, instructions, attendus, adaptateur, tokens_max)


def ecrire_rapport(
    resultats: list[ResultatEvaluation], chemin: Path = Path("outputs/evaluation.json")
) -> Path:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(
        json.dumps([r.en_dict() for r in resultats], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return chemin
