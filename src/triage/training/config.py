"""Hyperparametres de l'entrainement.

Regroupes dans une dataclasse plutot qu'eparpilles dans un script : chaque run
enregistre cette configuration telle quelle dans MLflow, ce qui rend un
resultat rejouable a l'identique.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Final

MODELE_BASE: Final[str] = "Qwen/Qwen3-1.7B-Base"

# Mesure sur les 5 000 exemples (voir notebooks/02) : p50 = 332 tokens,
# p99 = 988. A 1 024, 0,66 % des exemples sont tronques ; passer a 1 536 ne
# recupererait que 0,64 % de plus pour 50 % de VRAM d'activations en sus.
LONGUEUR_MAX: Final[int] = 1024

# Les sept projections d'un bloc Qwen3. Cibler l'attention seule (q, k, v, o)
# coute moins de memoire mais adapte moins bien le modele a un domaine.
MODULES_LORA: Final[tuple[str, ...]] = (
    "q_proj",
    "k_proj",
    "v_proj",
    "o_proj",
    "gate_proj",
    "up_proj",
    "down_proj",
)


@dataclass
class ConfigSFT:
    """Configuration d'un run de fine-tuning supervise."""

    modele: str = MODELE_BASE
    sortie: Path = Path("outputs/sft")

    # LoRA
    rang: int = 16
    alpha: int = 32
    dropout: float = 0.05
    modules_cibles: tuple[str, ...] = MODULES_LORA

    # Optimisation
    epochs: float = 2.0
    taux_apprentissage: float = 2e-4
    planificateur: str = "cosine"
    part_echauffement: float = 0.03
    decroissance_poids: float = 0.01

    # Lot : 2 x 8 = 16 exemples par pas d'optimisation. La taille reelle est
    # contrainte par les 10 Go de la carte, l'accumulation compense.
    taille_lot: int = 2
    accumulation: int = 8
    longueur_max: int = LONGUEUR_MAX

    # Memoire
    bf16: bool = True
    checkpoint_gradient: bool = True

    # Suivi et reprise
    pas_evaluation: int = 50
    pas_journalisation: int = 10
    checkpoints_conserves: int = 3
    graine: int = 42

    experience_mlflow: str = "triage-sft"
    nom_run: str = ""

    def en_dict(self) -> dict[str, Any]:
        donnees = asdict(self)
        donnees["sortie"] = str(donnees["sortie"])
        donnees["modules_cibles"] = list(donnees["modules_cibles"])
        return donnees

    @property
    def lot_effectif(self) -> int:
        return self.taille_lot * self.accumulation


@dataclass
class ConfigDPO(ConfigSFT):
    """Configuration de l'alignement par preferences.

    Les valeurs par defaut divergent du SFT : le DPO part d'un modele deja
    specialise et se degrade vite si on le pousse trop fort.
    """

    sortie: Path = Path("outputs/dpo")
    adaptateur_sft: Path = Path("outputs/sft/adaptateur")
    epochs: float = 1.0
    taux_apprentissage: float = 5e-6
    beta: float = 0.1
    experience_mlflow: str = "triage-dpo"
    modules_cibles: tuple[str, ...] = field(default=MODULES_LORA)
