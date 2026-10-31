"""Observer: flat float32 tensor with named views (PLAN.md 5.5, ACTIONS.md "Undo block").

Implements the observation side of R-216/R-217: the undo_block view exposes L's card type and B*
(plus the in-flight block and pre-effect board while a swap is being resolved), so the legal
masks are a function of the observation. Perfect information; per-player views are seat-relative
(observer at row 0, then p+1, p+2 in turn order).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
import numpy.typing as npt

from kingisdead import constants as C

if TYPE_CHECKING:
    from kingisdead.game import KingIsDeadState

NUM_CARDS = len(C.CARD_NAMES)
MODES = 4
PICK_SLOTS = 3
MAX_PLAYS_PER_SEAT = sum(C.STARTING_HAND.values())
CONTROL_KINDS = C.NUM_FACTIONS + 2  # none, S, W, E, unstable
CODES = C.NUM_FACTIONS + 1  # control faction + 1 one-hot width

Layout = list[tuple[str, tuple[int, ...]]]


def _layout(n: int) -> Layout:
    board = C.NUM_REGIONS * C.NUM_FACTIONS
    return [
        ("region_counts", (C.NUM_REGIONS, C.NUM_FACTIONS)),
        ("region_control", (C.NUM_REGIONS, CONTROL_KINDS)),
        ("region_states", (C.NUM_REGIONS, 3)),
        ("slots", (C.NUM_REGIONS, C.NUM_REGIONS + 1)),  # region on each slot, in slot order
        ("face_down", (C.NUM_REGIONS,)),
        ("struggles_resolved", (1,)),
        ("supply", (C.NUM_FACTIONS,)),
        ("courts", (n, C.NUM_FACTIONS)),
        ("hands", (n, NUM_CARDS)),
        # placement (n x (none + region)), availability (n), owner per slot (slot x n)
        ("discs", (n * (C.NUM_REGIONS + 1) + n + C.NUM_REGIONS * n,)),
        ("recent_win", (C.NUM_FACTIONS,)),
        ("order", (n, 5)),  # has_last, last_play, has_empty, hand_empty, plays_total (scaled)
        ("pass_count", (1,)),
        ("to_move", (n,)),
        (
            "phase",
            (
                C.NUM_STAGES
                + C.NUM_PHASES
                + (NUM_CARDS + 1)
                + MODES
                + PICK_SLOTS * (C.NUM_REGIONS + C.NUM_FACTIONS)
                + C.NUM_FACTIONS
                + 2 * C.NUM_REGIONS,
            ),
        ),
        (
            "undo_block",
            # L one-hot (0 = none); then three records (B*, swap_block, swap_start), each a
            # presence flag + counts + (state one-hot, control one-hot) per region.
            ((NUM_CARDS + 1) + 3 + 3 * board + 3 * C.NUM_REGIONS * (3 + CODES),),
        ),
    ]


class KingIsDeadObserver:
    """Flat float32 tensor with named views (perfect information)."""

    def __init__(self, num_players: int, params: dict[str, Any] | None) -> None:
        if params:
            raise ValueError(f"Observation parameters not supported; passed {params}")
        self.n = num_players
        shapes = _layout(num_players)
        size = sum(int(np.prod(s)) for _, s in shapes)
        self.tensor = np.zeros(size, np.float32)
        self.dict: dict[str, npt.NDArray[np.float32]] = {}
        index = 0
        for name, shape in shapes:
            length = int(np.prod(shape))
            self.dict[name] = self.tensor[index : index + length].reshape(shape)
            index += length

    def _rel(self, seat: int, player: int) -> int:
        return (seat - player) % self.n

    def set_from(self, state: KingIsDeadState, player: int) -> None:
        n, d = self.n, self.dict
        self.tensor.fill(0)
        d["region_counts"][:] = state.region_counts
        for r in range(C.NUM_REGIONS):
            if state.region_states[r] == C.REGION_UNSTABLE:
                d["region_control"][r, CONTROL_KINDS - 1] = 1
            else:
                d["region_control"][r, state.region_control[r] + 1] = 1
            d["region_states"][r, state.region_states[r]] = 1
            slot = state.slot_regions[r]
            d["slots"][r, 0 if slot is None else slot + 1] = 1
            d["face_down"][r] = r < state.struggles_resolved
        d["struggles_resolved"][0] = state.struggles_resolved
        d["supply"][:] = state.supply
        scale = float(MAX_PLAYS_PER_SEAT * n)
        discs = d["discs"]
        width = C.NUM_REGIONS + 1
        for seat in range(n):
            k = self._rel(seat, player)
            d["courts"][k] = state.courts[seat]
            for card, cnt in state.hands[seat].items():
                d["hands"][k, card - 1] = cnt
            reg = state.negotiation_discs[seat]
            discs[k * width + (0 if reg is None else reg + 1)] = 1
            discs[n * width + k] = 1.0 if reg is None else 0.0
            if reg is not None:
                for slot, sr in enumerate(state.slot_regions):
                    if sr == reg:
                        discs[n * width + n + slot * n + k] = 1
            lp, he = state.last_play[seat], state.hand_empty[seat]
            row = d["order"][k]
            row[0], row[1] = (0.0, 0.0) if lp is None else (1.0, lp / scale)
            row[2], row[3] = (0.0, 0.0) if he is None else (1.0, he / scale)
            row[4] = state.plays_total / scale
        for f in range(C.NUM_FACTIONS):
            d["recent_win"][f] = state.recent_win[f] + 1
        d["pass_count"][0] = state.pass_count
        if state.current_player() >= 0:
            d["to_move"][self._rel(state.to_move, player)] = 1
        self._set_phase(state)
        self._set_undo(state)

    def _set_phase(self, state: KingIsDeadState) -> None:
        ph = self.dict["phase"]
        o = 0
        ph[o + state.stage] = 1
        o += C.NUM_STAGES
        ph[o + state.phase] = 1
        o += C.NUM_PHASES
        ph[o + state.pending_card] = 1
        o += NUM_CARDS + 1
        ph[o + state.swap_mode] = 1
        o += MODES
        for i, (r, f) in enumerate(state.swap_picks[:PICK_SLOTS]):
            base = o + i * (C.NUM_REGIONS + C.NUM_FACTIONS)
            ph[base + r] = 1
            ph[base + C.NUM_REGIONS + f] = 1
        o += PICK_SLOTS * (C.NUM_REGIONS + C.NUM_FACTIONS)
        if state.phase == C.PHASE_ASSEMBLE:
            ph[o + state.assemble_faction] = 1
        o += C.NUM_FACTIONS
        if state.phase in (C.PHASE_NEG_SECOND, C.PHASE_NEG_DISC):
            ph[o + state.neg_first] = 1
        o += C.NUM_REGIONS
        if state.phase == C.PHASE_NEG_DISC:
            ph[o + state.neg_second] = 1

    def _set_undo(self, state: KingIsDeadState) -> None:
        u = self.dict["undo_block"]
        u[state.last_card or 0] = 1
        o = NUM_CARDS + 1
        board = C.NUM_REGIONS * C.NUM_FACTIONS
        sig_len = C.NUM_REGIONS * (3 + CODES)
        sig_now = self._sig(state.region_states, state.region_control)
        records: list[tuple[Any, Any]] = []
        ref = state.reference_board
        records.append((ref[0], ref[1]) if ref else (None, None))
        records.append((state.swap_block, "now"))  # a block applies only to the current signature
        ss = state.swap_start
        records.append((ss[0], ss[1]) if ss else (None, None))
        for counts, sig in records:
            if counts is not None:
                u[o] = 1
                u[o + 1 : o + 1 + board] = np.asarray(counts, np.float32).reshape(-1)
                if sig is not None:
                    u[o + 1 + board : o + 1 + board + sig_len] = (
                        sig_now if isinstance(sig, str) else self._sig_codes(sig)
                    )
            o += 1 + board + sig_len

    @staticmethod
    def _sig(states: Any, control: Any) -> npt.NDArray[np.float32]:
        out = np.zeros((C.NUM_REGIONS, 3 + CODES), np.float32)
        for r in range(C.NUM_REGIONS):
            out[r, states[r]] = 1
            out[r, 3 + control[r] + 1] = 1
        return out.reshape(-1)

    @staticmethod
    def _sig_codes(sig: tuple[int, ...]) -> npt.NDArray[np.float32]:
        """Decode rules.state_signature codes: 0 open, else (control + 1) * 10 + state."""
        out = np.zeros((C.NUM_REGIONS, 3 + CODES), np.float32)
        for r, code in enumerate(sig):
            out[r, code % 10] = 1
            out[r, 3 + code // 10] = 1
        return out.reshape(-1)

    def string_from(self, state: KingIsDeadState, player: int) -> str:
        """Readable debug view; every exposed field (including B*) appears."""
        self.set_from(state, player)
        parts = [f"p{player}"]
        for name, view in self.dict.items():
            vals = [f"{float(x):g}" for x in view.reshape(-1)]
            parts.append(f"{name}={' '.join(vals)}")
        return " | ".join(parts)
