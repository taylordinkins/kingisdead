"""King is Dead adapter: state -> JSON view, action metadata, scoring breakdown."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pyspiel

from kingisdead import actions as act
from kingisdead import constants as C
from kingisdead import rules
from kingisdead.game import GAME_SHORT_NAME, KingIsDeadState
from server.adapters.base import JSON, GameAdapter

PHASE_NAMES = {
    C.PHASE_TURN_START: "turn_start",
    C.PHASE_SUPPORT_TARGET: "support_target",
    C.PHASE_SUMMON: "summon",
    C.PHASE_ASSEMBLE: "assemble",
    C.PHASE_NEG_FIRST: "negotiate_first",
    C.PHASE_NEG_SECOND: "negotiate_second",
    C.PHASE_NEG_DISC: "negotiate_disc",
    C.PHASE_SWAP: "swap",
}
STAGE_NAMES = {
    C.STAGE_PICKS: "setup_region_cards",
    C.STAGE_COURTS: "setup_courts",
    C.STAGE_FILL: "setup_fill",
    C.STAGE_DONE: "play",
}


def _kid(state: pyspiel.State) -> KingIsDeadState:
    assert isinstance(state, KingIsDeadState)
    return state


def _narrow(tied: list[int], values: Sequence[int | None], best: str) -> list[int]:
    """Players of `tied` with the best value; None never wins; all stay if nobody has one."""
    have = [p for p in tied if values[p] is not None]
    if not have:
        return tied
    nums = [v for v in (values[p] for p in have) if v is not None]
    target = max(nums) if best == "max" else min(nums)
    return [p for p in have if values[p] == target]


def scoring_breakdown(state: KingIsDeadState) -> JSON:
    """Each ranking and tiebreak step (R-402..R-404), built from the public rule functions."""
    n = state.n
    players = list(range(n))
    steps: list[JSON] = []
    tied = players

    def step(name: str, values: Sequence[int | None], best: str, faction: int | None = None):
        nonlocal tied
        before = tied
        if len(before) > 1:
            tied = _narrow(before, values, best)
        steps.append(
            {"name": name, "faction": faction, "values": list(values), "tied_before": before,
             "remaining": tied}
        )  # fmt: skip

    if rules.is_invasion(state.region_states):
        step("complete_sets", [rules.complete_sets(c) for c in state.courts], "max")
        step("last_play", state.last_play, "max")
        return {"mode": "invasion", "steps": steps, "winners": state.winners()}
    ranking = rules.coronation_ranking(state.region_states, state.region_control, state.recent_win)
    controlled = [
        sum(
            1
            for r in range(C.NUM_REGIONS)
            if state.region_states[r] == C.REGION_CONTROLLED and state.region_control[r] == f
        )
        for f in range(C.NUM_FACTIONS)
    ]
    for i, f in enumerate(ranking[:2]):
        if f is not None:
            step(f"rank_{i + 1}_followers", [c[f] for c in state.courts], "max", f)
        else:
            steps.append({"name": f"rank_{i + 1}_followers", "faction": None, "skipped": True})
    step("hand_emptied", state.hand_empty, "min")
    return {
        "mode": "coronation",
        "faction_ranking": ranking,
        "regions_controlled": controlled,
        "recent_win": list(state.recent_win),
        "steps": steps,
        "winners": state.winners(),
    }


class KingIsDeadAdapter(GameAdapter):
    name = "king-is-dead"

    def load(self, params: dict[str, Any]) -> pyspiel.Game:
        n = int(params.get("players", 2))
        return pyspiel.load_game(f"{GAME_SHORT_NAME}(players={n})")

    def action_meta(self, state: pyspiel.State, action_id: int) -> JSON:
        d = act.decode_action(action_id)
        meta: JSON = {"label": act.action_label(action_id), "kind": d.kind.lower()}
        for key in ("region", "faction", "card"):
            value = getattr(d, key)
            if value is not None:
                meta[key] = value
        return meta

    def view(self, state: pyspiel.State, seat: int) -> JSON:
        s = _kid(state)
        terminal = s.is_terminal()
        chance = s.is_chance_node()
        track = [
            {
                "slot": i,
                "region": region,
                "face_down": i < s.struggles_resolved,
                "discs": [p for p in range(s.n) if region is not None
                          and s.negotiation_discs[p] == region],
            }
            for i, region in enumerate(s.slot_regions)
        ]  # fmt: skip
        regions = [
            {
                "region": r,
                "name": C.REGION_NAMES[r],
                "followers": list(s.region_counts[r]),
                "state": ("open", "controlled", "unstable")[s.region_states[r]],
                "controller": s.region_control[r] if s.region_states[r] == 1 else None,
            }
            for r in range(C.NUM_REGIONS)
        ]
        current = None if chance or terminal else s.current_player()
        view: JSON = {
            "seat": seat,
            "num_players": s.n,
            "regions": regions,
            "track": track,
            "supply": list(s.supply),
            "courts": [list(c) for c in s.courts],
            "hands": [{str(c): k for c, k in sorted(h.items()) if k} for h in s.hands],
            "negotiation_discs": list(s.negotiation_discs),
            "current_player": current,
            "is_chance": chance,
            "is_terminal": terminal,
            "stage": STAGE_NAMES[s.stage],
            "phase": PHASE_NAMES[s.phase],
            "pending": {
                "card": s.pending_card or None,
                "assemble_faction": s.assemble_faction if s.phase == C.PHASE_ASSEMBLE else None,
                "neg_first": s.neg_first if s.phase >= C.PHASE_NEG_SECOND else None,
                "neg_second": s.neg_second if s.phase == C.PHASE_NEG_DISC else None,
                "swap_mode": s.swap_mode,
                "swap_picks": [list(p) for p in s.swap_picks],
            },
            "consecutive_passes": s.pass_count,
            "struggles_resolved": s.struggles_resolved,
            "legal_actions": [
                {"id": a, **self.action_meta(s, a)} for a in s.legal_actions()
            ] if current is not None else [],
        }  # fmt: skip
        if terminal:
            view["returns"] = s.returns()
            view["winners"] = s.winners()
            view["scoring"] = scoring_breakdown(s)
        return view
