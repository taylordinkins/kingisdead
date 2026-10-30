"""Toy OpenSpiel game shaped like the future King is Dead game (Phase 0 API spike).

Registered as ``python_kid_toy``. It exists only to exercise the OpenSpiel 2.0.2 Python-game
API (see docs/OPENSPIEL_NOTES.md); it is not part of the real game.

Rules (invented for the spike):
- A bag holds ``_BAG_COUNTS`` tokens in three colours. Setup chance nodes deal two tokens to
  each player in seat order; each draw is weighted by the remaining bag counts (non-uniform
  and state dependent).
- Players then alternate seats for ``_TOKENS_PER_PLAYER`` rounds. A turn is two consecutive
  decisions by the same player: pick a colour from their hand (actions 0-2), then pick a
  target slot (actions 3-5). Score gain is (colour + 1) * (target + 1).
- When every token is played, the players with the highest score share the win: with n
  players and k winners, winners get (n - k) / (k * (n - 1)) and losers -1 / (n - 1).
"""

from __future__ import annotations

import numpy as np
import pyspiel

NUM_COLOURS = 3
NUM_TARGETS = 3
TOKENS_PER_PLAYER = 2
BAG_COUNTS = (3, 3, 3)
MIN_PLAYERS = 2
MAX_PLAYERS = 3
DEFAULT_PLAYERS = 2

PICK_BASE = 0  # actions 0..2: choose colour
TARGET_BASE = NUM_COLOURS  # actions 3..5: choose target

GAME_TYPE = pyspiel.GameType(
    short_name="python_kid_toy",
    long_name="Python KID Toy",
    dynamics=pyspiel.GameType.Dynamics.SEQUENTIAL,
    chance_mode=pyspiel.GameType.ChanceMode.EXPLICIT_STOCHASTIC,
    information=pyspiel.GameType.Information.PERFECT_INFORMATION,
    utility=pyspiel.GameType.Utility.ZERO_SUM,
    reward_model=pyspiel.GameType.RewardModel.TERMINAL,
    max_num_players=MAX_PLAYERS,
    min_num_players=MIN_PLAYERS,
    provides_information_state_string=False,
    provides_information_state_tensor=False,
    provides_observation_string=True,
    provides_observation_tensor=True,
    parameter_specification={"players": DEFAULT_PLAYERS},
)


def max_game_length(num_players: int) -> int:
    """Player decisions only (pick + target per token); chance nodes are NOT counted."""
    return num_players * TOKENS_PER_PLAYER * 2


def max_chance_nodes(num_players: int) -> int:
    """Setup draws. Optional override; the default bound is max_game_length."""
    return num_players * TOKENS_PER_PLAYER


def observation_size(num_players: int) -> int:
    """hands + bag + scores + pending colour + current player."""
    return num_players * NUM_COLOURS + NUM_COLOURS + num_players + NUM_COLOURS + num_players


class ToyGame(pyspiel.Game):
    def __init__(self, params: dict | None = None) -> None:
        params = dict(params or {})
        num_players = int(params.get("players", DEFAULT_PLAYERS))
        # load_game does not enforce min/max_num_players for Python games; validate here.
        if not MIN_PLAYERS <= num_players <= MAX_PLAYERS:
            raise ValueError(
                f"players must be in [{MIN_PLAYERS}, {MAX_PLAYERS}], got {num_players}"
            )
        game_info = pyspiel.GameInfo(
            num_distinct_actions=NUM_COLOURS + NUM_TARGETS,
            max_chance_outcomes=NUM_COLOURS,
            num_players=num_players,
            min_utility=-1.0 / (num_players - 1),
            max_utility=1.0,
            utility_sum=0.0,
            max_game_length=max_game_length(num_players),
        )
        super().__init__(GAME_TYPE, game_info, params)
        self.n = num_players

    def max_chance_nodes_in_history(self) -> int:
        return max_chance_nodes(self.n)

    def new_initial_state(self) -> ToyState:
        return ToyState(self)

    def make_py_observer(self, iig_obs_type=None, params=None) -> ToyObserver:
        return ToyObserver(self.n, params)


class ToyState(pyspiel.State):
    def __init__(self, game: ToyGame) -> None:
        super().__init__(game)
        self.n = game.n
        self.bag = list(BAG_COUNTS)
        self.hands = [[0] * NUM_COLOURS for _ in range(self.n)]
        self.scores = [0] * self.n
        self.pending_colour: int | None = None
        self.to_move = 0
        self.tokens_played = 0
        self.draws = 0

    # -- flow -------------------------------------------------------------------------------
    def _setup_done(self) -> bool:
        return self.draws >= self.n * TOKENS_PER_PLAYER

    def is_terminal(self) -> bool:
        return self.tokens_played >= self.n * TOKENS_PER_PLAYER

    def current_player(self) -> int:
        if self.is_terminal():
            return pyspiel.PlayerId.TERMINAL
        if not self._setup_done():
            return pyspiel.PlayerId.CHANCE
        return self.to_move

    def _legal_actions(self, player: int) -> list[int]:
        if self.pending_colour is None:
            return [PICK_BASE + c for c in range(NUM_COLOURS) if self.hands[player][c] > 0]
        return [TARGET_BASE + t for t in range(NUM_TARGETS)]

    def chance_outcomes(self) -> list[tuple[int, float]]:
        total = sum(self.bag)
        return [(c, n / total) for c, n in enumerate(self.bag) if n > 0]

    def _apply_action(self, action: int) -> None:
        if not self._setup_done():
            self.bag[action] -= 1
            self.hands[self.draws // TOKENS_PER_PLAYER][action] += 1
            self.draws += 1
        elif self.pending_colour is None:
            self.pending_colour = action - PICK_BASE
        else:
            target = action - TARGET_BASE
            colour = self.pending_colour
            self.hands[self.to_move][colour] -= 1
            self.scores[self.to_move] += (colour + 1) * (target + 1)
            self.pending_colour = None
            self.tokens_played += 1
            # The seat advances only after the target, so one player decides twice in a row.
            self.to_move = (self.to_move + 1) % self.n

    def _action_to_string(self, player: int, action: int) -> str:
        if player == pyspiel.PlayerId.CHANCE:
            return f"Draw:{action}"
        if action < TARGET_BASE:
            return f"Pick:{action - PICK_BASE}"
        return f"Target:{action - TARGET_BASE}"

    # -- outcome ----------------------------------------------------------------------------
    def returns(self) -> list[float]:
        if not self.is_terminal():
            return [0.0] * self.n
        best = max(self.scores)
        winners = [p for p in range(self.n) if self.scores[p] == best]
        k, n = len(winners), self.n
        win = (n - k) / (k * (n - 1))
        lose = -1.0 / (n - 1)
        return [win if p in winners else lose for p in range(n)]

    def __str__(self) -> str:
        return (
            f"bag={self.bag} hands={self.hands} scores={self.scores} "
            f"pending={self.pending_colour} to_move={self.to_move}"
        )


class ToyObserver:
    """PyObserver: one flat float32 ``tensor`` plus named reshaped views in ``dict``."""

    def __init__(self, num_players: int, params: dict | None) -> None:
        if params:
            raise ValueError(f"Observation parameters not supported; passed {params}")
        self.n = num_players
        self.tensor = np.zeros(observation_size(num_players), np.float32)
        self.dict: dict[str, np.ndarray] = {}
        index = 0
        for name, shape in [
            ("hands", (num_players, NUM_COLOURS)),
            ("bag", (NUM_COLOURS,)),
            ("scores", (num_players,)),
            ("pending", (NUM_COLOURS,)),
            ("to_move", (num_players,)),
        ]:
            size = int(np.prod(shape))
            self.dict[name] = self.tensor[index : index + size].reshape(shape)
            index += size

    def _seat(self, player: int, seat: int) -> int:
        """Seat index relative to the observer (own seat first)."""
        return (seat - player) % self.n

    def set_from(self, state: ToyState, player: int) -> None:
        self.tensor.fill(0)
        for seat in range(self.n):
            rel = self._seat(player, seat)
            self.dict["hands"][rel] = state.hands[seat]
            self.dict["scores"][rel] = state.scores[seat]
        self.dict["bag"][:] = state.bag
        if state.pending_colour is not None:
            self.dict["pending"][state.pending_colour] = 1
        if not state.is_terminal() and state._setup_done():
            self.dict["to_move"][self._seat(player, state.to_move)] = 1

    def string_from(self, state: ToyState, player: int) -> str:
        return f"p{player} {state}"


pyspiel.register_game(GAME_TYPE, ToyGame)
