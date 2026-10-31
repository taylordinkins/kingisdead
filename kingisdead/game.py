"""OpenSpiel adapter: game registration, setup chance nodes and turn skeleton.

Implements R-007, R-010..R-015, R-100 (and the TURN_START mask of R-101/R-103).
Card sub-steps, struggles and scoring belong to later units and raise NotImplementedError.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import numpy.typing as npt
import pyspiel

from kingisdead import actions as act
from kingisdead import constants as C

GAME_SHORT_NAME = "python_king_is_dead"
MIN_PLAYERS = 2
MAX_PLAYERS = 3
DEFAULT_PLAYERS = 2

# Setup stages (R-010 .. R-013).
STAGE_PICKS = 0
STAGE_COURTS = 1
STAGE_FILL = 2
STAGE_DONE = 3

REGION_FILL_TARGET = 4  # R-013
COURT_DRAWS_PER_PLAYER = 2  # R-012
HOME_FOLLOWERS = 2  # R-011

GAME_TYPE = pyspiel.GameType(
    short_name=GAME_SHORT_NAME,
    long_name="The King is Dead",
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


def max_game_length(n: int) -> int:
    """Player decisions only (ACTIONS.md section 7): 40n + 8n^2."""
    return 40 * n + 8 * n * n


def max_chance_nodes(n: int) -> int:
    """ACTIONS.md section 3: 8 picks + 2n court draws + 26 fill draws."""
    return (
        8
        + COURT_DRAWS_PER_PLAYER * n
        + (C.NUM_REGIONS * REGION_FILL_TARGET - HOME_FOLLOWERS * C.NUM_FACTIONS)
    )


class KingIsDeadGame(pyspiel.Game):
    def __init__(self, params: dict[str, Any] | None = None) -> None:
        params = dict(params or {})
        n = int(params.get("players", DEFAULT_PLAYERS))
        if not MIN_PLAYERS <= n <= MAX_PLAYERS:  # R-007
            raise ValueError(f"players must be {MIN_PLAYERS} or {MAX_PLAYERS}, got {n}")
        info = pyspiel.GameInfo(
            num_distinct_actions=act.NUM_DISTINCT_ACTIONS,
            max_chance_outcomes=act.MAX_CHANCE_OUTCOMES,
            num_players=n,
            min_utility=-1.0 / (n - 1),
            max_utility=1.0,
            utility_sum=0.0,
            max_game_length=max_game_length(n),
        )
        super().__init__(GAME_TYPE, info, params)
        self.n = n

    def max_chance_nodes_in_history(self) -> int:
        return max_chance_nodes(self.n)

    def new_initial_state(self) -> KingIsDeadState:
        return KingIsDeadState(self)

    def make_py_observer(
        self, iig_obs_type: object = None, params: dict[str, Any] | None = None
    ) -> KingIsDeadObserver:
        return KingIsDeadObserver(self.n, params)


class KingIsDeadState(pyspiel.State):
    def __init__(self, game: KingIsDeadGame) -> None:
        super().__init__(game)
        n = game.n
        self.n = n
        pool = C.FOLLOWERS_PER_FACTION[n]
        # R-011: home followers placed before any draw, taken from the pool (R-005).
        self.region_counts: list[list[int]] = [[0] * C.NUM_FACTIONS for _ in range(C.NUM_REGIONS)]
        for f, r in enumerate(C.HOME_REGION):
            self.region_counts[r][f] = HOME_FOLLOWERS
        self.courts: list[list[int]] = [[0] * C.NUM_FACTIONS for _ in range(n)]
        # supply is the bag during setup (R-012).
        self.supply: list[int] = [pool - HOME_FOLLOWERS] * C.NUM_FACTIONS
        self.slot_regions: list[int | None] = [None] * C.NUM_REGIONS
        self.region_states: list[int] = [C.REGION_OPEN] * C.NUM_REGIONS
        self.region_control: list[int] = [-1] * C.NUM_REGIONS  # controlling faction, -1 if none
        self.negotiation_discs: list[int | None] = [None] * n
        self.pass_count = 0
        self.struggles_resolved = 0
        self.plays_total = 0
        self.hands: list[dict[int, int]] = [dict(C.STARTING_HAND) for _ in range(n)]
        # R-401 records and R-216 data.
        self.last_play: list[int | None] = [None] * n
        self.hand_empty: list[int | None] = [None] * n
        self.recent_win: list[int] = [-1] * C.NUM_FACTIONS
        self.last_card: int | None = None
        self.reference_board: tuple[tuple[tuple[int, ...], ...], tuple[int, ...]] | None = None
        # Turn skeleton.
        self.to_move = 0
        self.stage = STAGE_PICKS
        self.setup_picks = 0
        self.court_draws = 0
        self.fill_region = 0

    # -- flow -------------------------------------------------------------------------------
    def is_terminal(self) -> bool:
        return False  # game end (R-304, R-400) arrives with the struggle unit

    def current_player(self) -> int:
        if self.stage != STAGE_DONE:
            return pyspiel.PlayerId.CHANCE
        return self.to_move

    def _legal_actions(self, player: int) -> list[int]:
        """TURN_START mask (R-101, R-103): PASS, then each card still in hand."""
        acts = [act.PASS]
        acts.extend(act.play_action(c) for c in sorted(self.hands[player]) if self.hands[player][c])
        return acts

    # -- setup chance (R-010..R-013) --------------------------------------------------------
    def chance_outcomes(self) -> list[tuple[int, float]]:
        if self.stage == STAGE_PICKS:
            free = [r for r in range(C.NUM_REGIONS) if r not in self.slot_regions]
            return [(act.encode_chance_outcome(r, "region"), 1.0 / len(free)) for r in free]
        total = sum(self.supply)
        return [
            (act.encode_chance_outcome(f, "faction"), c / total)
            for f, c in enumerate(self.supply)
            if c > 0
        ]

    def _advance_fill(self) -> None:
        while self.fill_region < C.NUM_REGIONS and (
            sum(self.region_counts[self.fill_region]) >= REGION_FILL_TARGET
        ):
            self.fill_region += 1
        if self.fill_region >= C.NUM_REGIONS:
            self.stage = STAGE_DONE

    def _apply_chance(self, outcome: int) -> None:
        if self.stage == STAGE_PICKS:
            if outcome in self.slot_regions:
                raise ValueError(f"region {outcome} already placed")
            self.slot_regions[self.setup_picks] = outcome
            self.setup_picks += 1
            if self.setup_picks == C.NUM_REGIONS:
                self.stage = STAGE_COURTS
            return
        f = act.decode_chance_outcome(outcome, "faction")
        if self.supply[f] <= 0:
            raise ValueError(f"no faction {f} follower left in the bag")
        self.supply[f] -= 1
        if self.stage == STAGE_COURTS:
            self.courts[self.court_draws // COURT_DRAWS_PER_PLAYER][f] += 1
            self.court_draws += 1
            if self.court_draws == COURT_DRAWS_PER_PLAYER * self.n:
                self.stage = STAGE_FILL
                self._advance_fill()
        else:
            self.region_counts[self.fill_region][f] += 1
            self._advance_fill()

    # -- turn (R-100..R-103) ----------------------------------------------------------------
    def _apply_action(self, action: int) -> None:
        if self.stage != STAGE_DONE:
            self._apply_chance(action)
            return
        if action == act.PASS:
            self.pass_count += 1
            if self.pass_count >= self.n:
                raise NotImplementedError("power struggle (R-105, R-300..R-304): later unit")
            self.to_move = (self.to_move + 1) % self.n
            return
        raise NotImplementedError("card play (R-102, R-210..R-216): later unit")

    def _action_to_string(self, player: int, action: int) -> str:
        if player == pyspiel.PlayerId.CHANCE:
            if self.stage == STAGE_PICKS:
                return f"Card {C.REGION_NAMES[action]}"
            return f"Draw {C.FACTION_NAMES[action]}"
        return act.action_label(action)

    # -- outcome ----------------------------------------------------------------------------
    def returns(self) -> list[float]:
        return [0.0] * self.n  # R-405: zero until the game ends

    def __str__(self) -> str:
        return (
            f"stage={self.stage} to_move={self.to_move} regions={self.region_counts} "
            f"courts={self.courts} supply={self.supply} slots={self.slot_regions} "
            f"states={self.region_states} passes={self.pass_count}"
        )


class KingIsDeadObserver:
    """Flat float32 tensor with named views (perfect information)."""

    def __init__(self, num_players: int, params: dict[str, Any] | None) -> None:
        if params:
            raise ValueError(f"Observation parameters not supported; passed {params}")
        self.n = num_players
        shapes = [
            ("region_counts", (C.NUM_REGIONS, C.NUM_FACTIONS)),
            ("courts", (num_players, C.NUM_FACTIONS)),
            ("supply", (C.NUM_FACTIONS,)),
            ("region_states", (C.NUM_REGIONS,)),
            ("to_move", (num_players,)),
        ]
        size = sum(int(np.prod(s)) for _, s in shapes)
        self.tensor = np.zeros(size, np.float32)
        self.dict: dict[str, npt.NDArray[np.float32]] = {}
        index = 0
        for name, shape in shapes:
            length = int(np.prod(shape))
            self.dict[name] = self.tensor[index : index + length].reshape(shape)
            index += length

    def set_from(self, state: KingIsDeadState, player: int) -> None:
        self.tensor.fill(0)
        self.dict["region_counts"][:] = state.region_counts
        for seat in range(self.n):
            self.dict["courts"][(seat - player) % self.n] = state.courts[seat]
        self.dict["supply"][:] = state.supply
        self.dict["region_states"][:] = state.region_states
        if state.stage == STAGE_DONE:
            self.dict["to_move"][(state.to_move - player) % self.n] = 1

    def string_from(self, state: KingIsDeadState, player: int) -> str:
        return f"p{player} {state}"


pyspiel.register_game(GAME_TYPE, KingIsDeadGame)
