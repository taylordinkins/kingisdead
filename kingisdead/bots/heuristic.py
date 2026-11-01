"""Greedy one-turn-lookahead heuristic bot (PLAN 5.8). No rule behaviour lives here."""

from __future__ import annotations

import random
from typing import Any

import pyspiel

from kingisdead import constants as C
from kingisdead import rules

TERMINAL_SCALE = 1000.0
W_RANK1 = 3.0  # followers of the projected rank-1 faction in my court (R-404)
W_RANK2 = 1.5  # followers of the projected rank-2 faction (R-404)
W_SETS = 4.0  # complete sets, weighted by how close an invasion is (R-402)
W_UNSTABLE = 1.0  # per projected unstable region, scales the invasion term


def _projection(s: Any) -> tuple[list[int], list[int], int]:
    """Region states/control if every unresolved struggle resolved on the current board (R-301)."""
    states = list(s.region_states)
    control = list(s.region_control)
    for slot in range(s.struggles_resolved, C.NUM_REGIONS):
        r = s.slot_regions[slot]
        if r is None:
            continue
        w = rules.struggle_winner(s.region_counts[r])
        if w is None:
            states[r] = C.REGION_UNSTABLE
        else:
            states[r] = C.REGION_CONTROLLED
            control[r] = w
    return states, control, sum(1 for x in states if x == C.REGION_UNSTABLE)


def _value(s: Any, player: int) -> float:
    states, control, unstable = _projection(s)
    recent = list(s.recent_win)
    ranking = rules.coronation_ranking(states, control, recent)
    invasion = min(unstable, C.INSTABILITY_DISCS) / C.INSTABILITY_DISCS
    out: list[float] = []
    for p in range(s.n):
        court = s.courts[p]
        v = W_SETS * rules.complete_sets(court) * invasion * invasion
        for weight, f in zip((W_RANK1, W_RANK2), ranking[:2], strict=True):
            if f is not None:
                v += weight * court[f] * (1.0 - 0.5 * invasion)
        out.append(v)
    others = [v for p, v in enumerate(out) if p != player]
    return out[player] - sum(others) / len(others)


def score_state(state: Any, player: int) -> float:
    """Score a position for `player`; higher is better."""
    if state.is_terminal():
        return TERMINAL_SCALE * state.returns()[player]
    return _value(state, player)


class HeuristicBot:
    def choose(self, state: pyspiel.State, rng: random.Random) -> int:
        legal = state.legal_actions()
        if len(legal) == 1:
            return legal[0]
        player = state.current_player()
        best: list[int] = []
        best_score = float("-inf")
        for a in legal:
            child = state.clone()
            child.apply_action(a)
            sc = score_state(child, player)
            if sc > best_score + 1e-9:
                best, best_score = [a], sc
            elif abs(sc - best_score) <= 1e-9:
                best.append(a)
        return rng.choice(best)
