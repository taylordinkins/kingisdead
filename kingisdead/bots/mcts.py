"""MCTS seat bot: a thin wrapper over OpenSpiel's MCTSBot with random rollouts (PLAN 5.8).

No rule behaviour lives here.
"""

from __future__ import annotations

import random
from typing import Any

import numpy as np
import pyspiel
from open_spiel.python.algorithms import mcts


class MCTSSeatBot:
    def __init__(self, simulations: int, uct_c: float = 2.0) -> None:
        self.simulations = simulations
        self.uct_c = uct_c

    def choose(self, state: pyspiel.State, rng: random.Random) -> int:
        legal = state.legal_actions()
        if len(legal) == 1:
            return legal[0]
        game: Any = getattr(state, "get_game")()  # noqa: B009  (stubs omit State.get_game)
        np_rng = np.random.RandomState(rng.getrandbits(32))
        bot: Any = mcts.MCTSBot(
            game,
            self.uct_c,
            self.simulations,
            mcts.RandomRolloutEvaluator(n_rollouts=1, random_state=np_rng),
            solve=False,
            random_state=np_rng,
        )
        action = int(bot.step(state.clone()))
        if action not in legal:
            raise ValueError(f"MCTS returned illegal action {action}")
        return action
