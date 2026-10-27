"""Limite de debit globale des routes qui declenchent un triage.

Globale et non par appelant : la cle d'API est partagee, elle ne distingue
personne. Le compteur vit en memoire, ce qui suffit parce que le deploiement
n'autorise qu'un conteneur pour l'API (cf. deploiement/modal_app.py). Il
repart de zero quand le conteneur s'eteint, sans consequence pour une demo.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class Plafond:
    """Au plus `appels` dans toute fenetre de `fenetre_s` secondes."""

    appels: int
    fenetre_s: float


# Un triage prend environ 2,3 s : 20 par minute laissent plusieurs personnes
# tester en meme temps, et 300 par jour bornent un script qui tournerait en boucle.
PLAFONDS_TRIAGE: Final[tuple[Plafond, ...]] = (
    Plafond(appels=20, fenetre_s=60),
    Plafond(appels=300, fenetre_s=24 * 60 * 60),
)


class LimiteDebit:
    """Fenetre glissante : on compte les appels des dernieres `fenetre_s` secondes.

    Le verrou est necessaire : FastAPI execute les routes synchrones dans un
    pool de threads, deux requetes peuvent donc tester le compteur en meme temps.
    """

    def __init__(
        self,
        plafonds: tuple[Plafond, ...] = PLAFONDS_TRIAGE,
        horloge: Callable[[], float] = time.monotonic,
    ) -> None:
        self._plafonds = plafonds
        self._horloge = horloge
        self._appels: deque[float] = deque()
        self._verrou = threading.Lock()

    def consommer(self) -> float | None:
        """Enregistre un appel s'il est permis.

        Renvoie None si l'appel passe, sinon le nombre de secondes a attendre
        avant qu'une place se libere (pour l'en-tete Retry-After).
        """
        with self._verrou:
            maintenant = self._horloge()
            fenetre_max = max(plafond.fenetre_s for plafond in self._plafonds)
            while self._appels and self._appels[0] <= maintenant - fenetre_max:
                self._appels.popleft()

            attente = 0.0
            for plafond in self._plafonds:
                recents = [t for t in self._appels if t > maintenant - plafond.fenetre_s]
                if len(recents) >= plafond.appels:
                    # La place se libere quand le plus ancien appel compte sort de la fenetre.
                    plus_ancien = recents[-plafond.appels]
                    attente = max(attente, plus_ancien + plafond.fenetre_s - maintenant)
            if attente > 0:
                return attente

            self._appels.append(maintenant)
            return None
