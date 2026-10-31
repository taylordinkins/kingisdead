"""OpenSpiel adapter: game registration, setup chance nodes and turn skeleton.

Implements R-007, R-010..R-015, R-100 (and the TURN_START mask of R-101/R-103).
Card sub-steps, struggles and scoring are implemented further down in this module.
"""

from __future__ import annotations

from typing import Any

import pyspiel

from kingisdead import actions as act
from kingisdead import constants as C
from kingisdead import rules
from kingisdead.constants import (  # noqa: F401  (re-exported)
    PHASE_ASSEMBLE,
    PHASE_NEG_DISC,
    PHASE_NEG_FIRST,
    PHASE_NEG_SECOND,
    PHASE_SUMMON,
    PHASE_SUPPORT_TARGET,
    PHASE_SWAP,
    PHASE_TURN_START,
    STAGE_COURTS,
    STAGE_DONE,
    STAGE_FILL,
    STAGE_PICKS,
)
from kingisdead.observer import KingIsDeadObserver

GAME_SHORT_NAME = "python_king_is_dead"
MIN_PLAYERS = 2
MAX_PLAYERS = 3
DEFAULT_PLAYERS = 2

CARD_ASSEMBLE = 4
CARD_NEGOTIATE = 5

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
        # B* (R-216): (followers per region and faction, state signature); None when nothing is
        # blocked or B* is void.
        self.reference_board: tuple[rules.Board, tuple[int, ...]] | None = None
        # Resolution of the current Manoeuvre / Outmanoeuvre (R-214..R-216).
        self.swap_mode = rules.MODE_NONE
        self.swap_picks: rules.Picks = ()
        self.swap_block: rules.Board | None = None  # B* followers if it applies to this play
        self.swap_start: tuple[rules.Board, tuple[int, ...]] | None = None  # board before effect
        # Turn skeleton.
        self.to_move = 0
        self.phase = PHASE_TURN_START
        self.pending_card = 0  # card being resolved while phase != TURN_START
        self.assemble_faction = 0  # faction being placed in PHASE_ASSEMBLE
        self.neg_first = 0  # first chosen region in NEG_SECOND / NEG_DISC
        self.neg_second = 0
        self.stage = STAGE_PICKS
        self.setup_picks = 0
        self.court_draws = 0
        self.fill_region = 0

    # -- flow -------------------------------------------------------------------------------
    def is_terminal(self) -> bool:
        """Implements R-304/R-400: third instability disc (invasion) or eighth struggle."""
        return self.stage == STAGE_DONE and rules.game_over(
            self.region_states, self.struggles_resolved
        )

    def current_player(self) -> int:
        if self.is_terminal():
            return pyspiel.PlayerId.TERMINAL
        if self.stage != STAGE_DONE:
            return pyspiel.PlayerId.CHANCE
        return self.to_move

    def _legal_actions(self, player: int) -> list[int]:
        """Mask per phase: TURN_START (R-101, R-103), SUPPORT_TARGET (R-210), SUMMON (R-201)."""
        if self.is_terminal():
            return []
        if self.phase == PHASE_SUPPORT_TARGET:
            return [act.region_action(r) for r in self._support_targets(self.pending_card)]
        if self.phase == PHASE_ASSEMBLE:
            return [
                act.region_action(r)
                for r in range(C.NUM_REGIONS)
                if self.region_states[r] == C.REGION_OPEN
            ]
        if self.phase == PHASE_NEG_FIRST:
            return [act.region_action(r) for r in rules.negotiate_first_options(self._neg_pool())]
        if self.phase == PHASE_NEG_SECOND:
            return [act.region_action(r) for r in self._neg_pool() if r > self.neg_first]
        if self.phase == PHASE_NEG_DISC:
            return [act.region_action(r) for r in (self.neg_first, self.neg_second)]
        if self.phase == PHASE_SWAP:
            nxt = rules.swap_next_picks(
                rules.board_of(self.region_counts), self.swap_mode, self.swap_block, self.swap_picks
            )
            return sorted(act.follower_action(r, f) for r, f in nxt)
        if self.phase == PHASE_SUMMON:
            return [act.follower_action(r, f) for r, f in rules.summon_options(self.region_counts)]
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
            outcome = act.decode_chance_outcome(outcome, "region")
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
        if action not in self._legal_actions(self.to_move):
            raise ValueError(f"action {action} is not legal in phase {self.phase}")
        if action == act.PASS:
            self.pass_count += 1
            if self.pass_count >= self.n:
                self._power_struggle()
            self.to_move = (self.to_move + 1) % self.n
            return
        d = act.decode_action(action)
        if self.phase in (PHASE_ASSEMBLE, PHASE_NEG_FIRST, PHASE_NEG_SECOND, PHASE_NEG_DISC):
            if d.kind != "REGION" or d.region is None or action not in self._legal_actions(0):
                raise ValueError(f"action {action} is not legal in phase {self.phase}")
            self._apply_region_step(d.region)
            return
        if self.phase == PHASE_SUPPORT_TARGET:
            if d.kind != "REGION" or d.region is None:
                raise ValueError(f"action {action} is not a support target")
            self._place_support(self.pending_card, d.region)
            self._enter_summon()
            return
        if self.phase == PHASE_SWAP:
            if action not in self._legal_actions(0):
                raise ValueError(f"action {action} is not legal in phase {self.phase}")
            assert d.region is not None and d.faction is not None
            self._swap_pick(d.region, d.faction)
            return
        if self.phase == PHASE_SUMMON:
            if d.kind != "FOLLOWER" or d.region is None or d.faction is None:
                raise ValueError(f"action {action} is not a summon choice")
            self._summon(d.region, d.faction)
            return
        if d.kind != "PLAY" or d.card is None:
            raise ValueError(f"action {action} is not legal at turn start")
        self._play_card(d.card)

    def _power_struggle(self) -> None:
        """Implements R-105, R-300..R-304. The caller advances to_move past the last passer."""
        slot = self.struggles_resolved
        region = self.slot_regions[slot]
        assert region is not None
        winner = rules.struggle_winner(self.region_counts[region])
        if winner is None:
            self.region_states[region] = C.REGION_UNSTABLE  # R-301
        else:
            self.region_states[region] = C.REGION_CONTROLLED
            self.region_control[region] = winner
            self.recent_win[winner] = slot + 1  # R-303
        for f in range(C.NUM_FACTIONS):  # R-302
            self.supply[f] += self.region_counts[region][f]
            self.region_counts[region][f] = 0
        self.struggles_resolved += 1
        self.pass_count = 0  # R-304

    def _neg_pool(self) -> list[int]:
        """Implements R-213: eligible cards."""
        return rules.negotiate_eligible(
            self.slot_regions, self.struggles_resolved, self.negotiation_discs
        )

    def _apply_region_step(self, r: int) -> None:
        """Implements R-212 (Assemble placements) and R-213 (Negotiate choices)."""
        if self.phase == PHASE_ASSEMBLE:
            f = self.assemble_faction
            self.supply[f] -= 1
            self.region_counts[r][f] += 1
            self._next_assemble(f)
        elif self.phase == PHASE_NEG_FIRST:
            self.neg_first = r
            self.phase = PHASE_NEG_SECOND
        elif self.phase == PHASE_NEG_SECOND:
            self.neg_second = r
            self.slot_regions = rules.negotiate_swap(self.slot_regions, self.neg_first, r)
            self.phase = PHASE_NEG_DISC
        else:
            self.negotiation_discs[self.to_move] = r
            self._enter_summon()

    def _next_assemble(self, after: int) -> None:
        """Implements R-212: advance to the next faction with supply, or on to the summon."""
        f = rules.next_assemble_faction(self.supply, after)
        if f is None:
            self._enter_summon()
        else:
            self.phase = PHASE_ASSEMBLE
            self.assemble_faction = f

    def _support_targets(self, card: int) -> list[int]:
        """Implements R-210/R-211: eligible regions, empty if the supply is exhausted."""
        f = rules.SUPPORT_FACTION[card]
        if self.supply[f] < 1:
            return []
        return rules.support_eligible_regions(f, self.region_states, self.region_control)

    def _place_support(self, card: int, region: int) -> None:
        """Implements R-211."""
        f = rules.SUPPORT_FACTION[card]
        if region not in self._support_targets(card):
            raise ValueError(f"region {region} is not eligible")
        n = rules.support_count(self.supply[f])
        self.supply[f] -= n
        self.region_counts[region][f] += n

    def _enter_summon(self) -> None:
        """Implements R-201: go to SUMMON, or skip it (and end the turn) on an empty board."""
        if rules.summon_options(self.region_counts):
            self.phase = PHASE_SUMMON
        else:
            self._end_turn()

    def _summon(self, region: int, faction: int) -> None:
        """Implements R-201."""
        if self.region_counts[region][faction] <= 0:
            raise ValueError("no such follower on the board")
        if self.swap_start is not None:  # R-216: complete B* now that L's summon is made
            before, sig = self.swap_start
            if before[region][faction] > 0:  # else D22: B* is void
                rows = [list(row) for row in before]
                rows[region][faction] -= 1
                self.reference_board = (tuple(tuple(row) for row in rows), sig)
            self.swap_start = None
        self.region_counts[region][faction] -= 1
        self.courts[self.to_move][faction] += 1
        self._end_turn()

    def _end_turn(self) -> None:
        self.phase = PHASE_TURN_START
        self.pending_card = 0
        self.to_move = (self.to_move + 1) % self.n

    def _play_card(self, card: int) -> None:
        """Implements R-102, R-104, R-202, R-210, R-211: spend the card, then resolve it.

        Manoeuvre and Outmanoeuvre are R-214..R-217 (see _start_swap).
        """
        hand = self.hands[self.to_move]
        if hand.get(card, 0) <= 0:
            raise ValueError(f"card {card} is not in hand")
        hand[card] -= 1
        self.plays_total += 1
        self.last_play[self.to_move] = self.plays_total  # R-401
        if not any(hand.values()):
            self.hand_empty[self.to_move] = self.plays_total
        self.pass_count = 0
        # R-217: any card play replaces L and B*; only a same-type play is blocked by the old B*.
        old_ref, old_card = self.reference_board, self.last_card
        self.last_card = card
        self.reference_board = None
        self.swap_start = None
        if card in (rules.MANOEUVRE, rules.OUTMANOEUVRE):
            self._start_swap(card, old_ref if old_card == card else None)
            return
        if card in rules.SUPPORT_FACTION and self._support_targets(card):
            self.phase = PHASE_SUPPORT_TARGET
            self.pending_card = card
            return
        self.pending_card = card
        if card == CARD_ASSEMBLE:
            self._next_assemble(-1)
            return
        if card == CARD_NEGOTIATE and len(self._neg_pool()) >= 2:
            self.phase = PHASE_NEG_FIRST
            return
        self.pending_card = 0
        self._enter_summon()

    def _start_swap(self, card: int, old_ref: tuple[rules.Board, tuple[int, ...]] | None) -> None:
        """Implements R-214, R-215, R-216: fix the form and capture B* if a swap will be made."""
        board = rules.board_of(self.region_counts)
        sig = rules.state_signature(self.region_states, self.region_control)
        block = old_ref[0] if old_ref is not None and old_ref[1] == sig else None
        self.pending_card = card
        self.swap_picks = ()
        self.swap_block = block
        self.swap_mode = rules.swap_mode(card, board, block)
        if self.swap_mode == rules.MODE_NONE:  # R-202: no effect, nothing becomes L's B*
            self.pending_card = 0
            self._enter_summon()
            return
        self.swap_start = (board, sig)
        self.phase = PHASE_SWAP

    def _swap_pick(self, region: int, faction: int) -> None:
        """Implements R-214, R-215: record a pick; apply the swap once it is complete."""
        self.swap_picks += ((region, faction),)
        if len(self.swap_picks) < rules.swap_length(self.swap_mode):
            return
        board = rules.apply_swap(
            rules.board_of(self.region_counts), self.swap_mode, self.swap_picks
        )
        self.region_counts = [list(row) for row in board]
        self.swap_picks = ()
        self.swap_block = None
        self.swap_mode = rules.MODE_NONE
        self.pending_card = 0
        self._enter_summon()

    def _action_to_string(self, player: int, action: int) -> str:
        """Chance labels are only meaningful at the node where the action is taken."""
        if player == pyspiel.PlayerId.CHANCE:
            if self.stage == STAGE_PICKS:
                return f"Card {C.REGION_NAMES[act.decode_chance_outcome(action, 'region')]}"
            return f"Draw {C.FACTION_NAMES[act.decode_chance_outcome(action, 'faction')]}"
        return act.action_label(action)

    # -- outcome ----------------------------------------------------------------------------
    def returns(self) -> list[float]:
        """Implements R-400..R-405: zero until the game ends, then the shared-win returns."""
        if not self.is_terminal():
            return [0.0] * self.n
        return rules.game_returns(self.n, self.winners())

    def player_return(self, player: int) -> float:
        return self.returns()[player]

    def winners(self) -> list[int]:
        """Implements R-402 (invasion) or R-403/R-404 (coronation) at a terminal state."""
        if rules.is_invasion(self.region_states):
            return rules.invasion_winners(self.courts, self.last_play)
        ranking = rules.coronation_ranking(self.region_states, self.region_control, self.recent_win)
        return rules.coronation_winners(self.courts, ranking, self.hand_empty)

    def __str__(self) -> str:
        return (
            f"stage={self.stage} to_move={self.to_move} regions={self.region_counts} "
            f"courts={self.courts} supply={self.supply} slots={self.slot_regions} "
            f"states={self.region_states} passes={self.pass_count}"
        )


pyspiel.register_game(GAME_TYPE, KingIsDeadGame)
