# pyright: basic
"""Scenario loader (docs/SCENARIOS.md): JSON position -> KingIsDeadState.

Implements the validation rules V1..V11 of SCENARIOS.md. Raises ValueError for a rejected scenario.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from kingisdead import constants as C
from kingisdead.game import STAGE_DONE, KingIsDeadGame, KingIsDeadState

FACTION_KEYS = {"S": 0, "W": 1, "E": 2}
CARD_IDS = {
    "scottish_support": 1,
    "welsh_support": 2,
    "english_support": 3,
    "assemble": 4,
    "negotiate": 5,
    "manoeuvre": 6,
    "outmanoeuvre": 7,
}
NEGOTIATE = CARD_IDS["negotiate"]
MANOEUVRE_CARDS = (CARD_IDS["manoeuvre"], CARD_IDS["outmanoeuvre"])
COMMON_KEYS = {"format", "kind", "description", "players", "slots", "regions", "courts", "example"}
STATE_KEYS = COMMON_KEYS | {
    "to_play",
    "struggles",
    "region_state",
    "negotiation",
    "hands",
    "pass_count",
    "last_play",
    "hand_empty",
    "last_card",
}
CARDS_PER_HAND = sum(C.STARTING_HAND.values())


def _fail(code: str, msg: str) -> ValueError:
    return ValueError(f"{code}: {msg}")


def _region(name: object) -> int:
    if not isinstance(name, str) or name not in C.REGION_NAMES:
        raise ValueError(f"unknown region {name!r}")
    return C.REGION_NAMES.index(name)


def _counts(m: object, what: str) -> list[int]:
    if not isinstance(m, dict):
        raise ValueError(f"{what}: count map expected")
    out = [0, 0, 0]
    for k, v in m.items():
        if k not in FACTION_KEYS:
            raise ValueError(f"{what}: unknown faction key {k!r}")
        if not isinstance(v, int) or isinstance(v, bool) or v < 0:
            raise ValueError(f"{what}: bad count {v!r}")
        out[FACTION_KEYS[k]] = v
    return out


def _region_map(m: object, what: str) -> list[list[int]]:
    if not isinstance(m, dict):
        raise ValueError(f"{what}: map expected")
    out = [[0, 0, 0] for _ in range(C.NUM_REGIONS)]
    for name, cm in m.items():
        out[_region(name)] = _counts(cm, f"{what}[{name}]")
    return out


def _state_map(m: object, what: str) -> tuple[list[int], list[int]]:
    """region_state map -> (states, controlling faction or -1)."""
    if not isinstance(m, dict):
        raise ValueError(f"{what}: map expected")
    states = [C.REGION_OPEN] * C.NUM_REGIONS
    control = [-1] * C.NUM_REGIONS
    for name, v in m.items():
        r = _region(name)
        if v == "unstable":
            states[r] = C.REGION_UNSTABLE
        elif v in FACTION_KEYS:
            states[r] = C.REGION_CONTROLLED
            control[r] = FACTION_KEYS[v]
        else:
            raise _fail("V5", f"bad region state {v!r}")
    return states, control


def _hand(cards: object) -> dict[int, int]:
    if not isinstance(cards, list):
        raise ValueError("hand: list expected")
    hand: dict[int, int] = {}
    for c in cards:
        if c not in CARD_IDS:
            raise ValueError(f"unknown card {c!r}")
        hand[CARD_IDS[c]] = hand.get(CARD_IDS[c], 0) + 1
    return hand


def _per_player(data: dict[str, Any], key: str, n: int, default: Any) -> list[Any]:
    if key not in data:
        return [default() if callable(default) else default for _ in range(n)]
    v = data[key]
    if not isinstance(v, list) or len(v) != n:
        raise ValueError(f"{key}: list of {n} entries expected")
    return list(v)


def _check_pool(regions: list[list[int]], courts: list[list[int]], pool: int, what: str) -> None:
    for f in range(C.NUM_FACTIONS):  # V1
        total = sum(row[f] for row in regions) + sum(row[f] for row in courts)
        if total > pool:
            raise _fail("V1", f"{what}: faction {f} has {total} followers, pool is {pool}")


def load_scenario(source: str | Path | dict[str, Any]) -> KingIsDeadState:
    """Build a state from a scenario path or parsed dict; ValueError if rejected."""
    data = source if isinstance(source, dict) else json.loads(Path(source).read_text())
    if not isinstance(data, dict):
        raise ValueError("scenario must be an object")
    if data.get("format") != 1:
        raise ValueError("format must be 1")
    kind = data.get("kind")
    if kind not in ("setup", "state"):
        raise ValueError(f"bad kind {kind!r}")
    unknown = set(data) - (COMMON_KEYS if kind == "setup" else STATE_KEYS)
    if unknown:
        raise ValueError(f"unknown keys {sorted(unknown)}")
    n = data.get("players")
    if n not in (2, 3):
        raise ValueError(f"players must be 2 or 3, got {n!r}")
    pool = C.FOLLOWERS_PER_FACTION[n]

    names = data.get("slots")
    if not isinstance(names, list) or len(names) != C.NUM_REGIONS:
        raise ValueError("slots: 8 region names expected")
    slots = [_region(x) for x in names]
    if sorted(slots) != list(range(C.NUM_REGIONS)):
        raise ValueError("slots must be a permutation of the 8 regions")
    regions = _region_map(data.get("regions", {}), "regions")
    courts = [_counts(c, "court") for c in _per_player(data, "courts", n, None)]
    if "courts" not in data:
        raise ValueError("courts required")
    _check_pool(regions, courts, pool, "board")

    if kind == "setup":
        _validate_setup(regions, courts)
        extra: dict[str, Any] = {}
    else:
        extra = _validate_state(data, n, pool, slots, regions, courts)

    state = KingIsDeadGame({"players": n}).new_initial_state()
    state.slot_regions = list(slots)
    state.region_counts = regions
    state.courts = courts
    state.supply = [
        pool - sum(r[f] for r in regions) - sum(c[f] for c in courts) for f in range(C.NUM_FACTIONS)
    ]
    state.stage = STAGE_DONE
    state.setup_picks = C.NUM_REGIONS
    state.court_draws = 2 * n
    state.fill_region = C.NUM_REGIONS
    for key, value in extra.items():
        setattr(state, key, value)
    return state


def _validate_setup(regions: list[list[int]], courts: list[list[int]]) -> None:
    """V11."""
    for r, row in enumerate(regions):
        if sum(row) != 4:
            raise _fail("V11", f"{C.REGION_NAMES[r]} holds {sum(row)} followers, expected 4")
    for f, home in enumerate(C.HOME_REGION):
        if regions[home][f] < 2:
            raise _fail("V11", f"{C.REGION_NAMES[home]} needs >= 2 {C.FACTION_NAMES[f]}")
    for c in courts:
        if sum(c) != 2:
            raise _fail("V11", "each court must hold exactly 2 followers")


def _validate_state(
    data: dict[str, Any],
    n: int,
    pool: int,
    slots: list[int],
    regions: list[list[int]],
    courts: list[list[int]],
) -> dict[str, Any]:
    states, control = _state_map(data.get("region_state", {}), "region_state")
    struggles = data.get("struggles", 0)
    if not isinstance(struggles, int) or not 0 <= struggles <= 8:
        raise ValueError("struggles must be 0..8")
    closed = [r for r in range(C.NUM_REGIONS) if states[r] != C.REGION_OPEN]
    unstable = [r for r in closed if states[r] == C.REGION_UNSTABLE]
    for r in closed:  # V2
        if any(regions[r]):
            raise _fail("V2", f"closed region {C.REGION_NAMES[r]} holds followers")
    if len(unstable) >= 3 and not (  # V3
        len(unstable) == 3 and struggles >= 1 and slots[struggles - 1] in unstable
    ):
        raise _fail("V3", "three unstable regions on a non-terminal board")
    if len(closed) != struggles or sorted(closed) != sorted(slots[:struggles]):  # V4
        raise _fail("V4", "closed regions must be exactly the regions in slots 1..struggles")

    hands = [_hand(h) for h in _per_player(data, "hands", n, None)] if "hands" in data else None
    hand_list = hands or [dict(C.STARTING_HAND) for _ in range(n)]
    for h in hand_list:  # V8
        for c, k in h.items():
            if k > C.STARTING_HAND[c]:
                raise _fail("V8", f"hand holds {k} copies of card {c}")
    sizes = [sum(h.values()) for h in hand_list]
    total = sum(CARDS_PER_HAND - s for s in sizes)

    neg_raw = _per_player(data, "negotiation", n, None)
    neg: list[int | None] = [None if x is None else _region(x) for x in neg_raw]
    named = [x for x in neg if x is not None]
    if len(set(named)) != len(named):  # V6
        raise _fail("V6", "two players name the same region")
    for p, x in enumerate(neg):
        if x is not None and hand_list[p].get(NEGOTIATE, 0) > 0:
            raise _fail("V6", f"player {p} has a spent disc but still holds negotiate")

    pass_count = data.get("pass_count", 0)  # V9
    if not isinstance(pass_count, int) or not 0 <= pass_count < n:
        raise _fail("V9", "pass_count must be < players")
    to_play = data.get("to_play", 0)
    if not isinstance(to_play, int) or not 0 <= to_play < n:
        raise ValueError("to_play out of range")

    last_play = _per_player(data, "last_play", n, None)
    hand_empty = _per_player(data, "hand_empty", n, None)
    _validate_records(last_play, hand_empty, sizes, total)  # V7

    last_card_raw = data.get("last_card")
    last_card: int | None = None
    ref: tuple[tuple[tuple[int, ...], ...], tuple[int, ...]] | None = None
    if (last_card_raw is None) != (total == 0):  # V10
        raise _fail("V10", "last_card must be null exactly when no card has been played")
    if last_card_raw is not None:
        if not isinstance(last_card_raw, dict) or last_card_raw.get("type") not in CARD_IDS:
            raise ValueError("last_card.type must be a card name")
        last_card = CARD_IDS[last_card_raw["type"]]
        mover = last_play.index(total)
        if hand_list[mover].get(last_card, 0) >= C.STARTING_HAND[last_card]:
            raise _fail("V10", "last_card type is still fully in the last player's hand")
        if "reference_board" in last_card_raw:
            if last_card not in MANOEUVRE_CARDS:
                raise _fail("V10", "reference_board only allowed for manoeuvre/outmanoeuvre")
            rb = last_card_raw["reference_board"]
            rb_regions = _region_map(rb.get("regions", {}), "reference_board.regions")
            rb_states, rb_control = _state_map(
                rb.get("region_state", {}), "reference_board.region_state"
            )
            _check_pool(rb_regions, courts, pool, "reference_board")
            for r in range(C.NUM_REGIONS):
                if rb_states[r] != C.REGION_OPEN and any(rb_regions[r]):
                    raise _fail("V2", "reference_board closed region holds followers")
            ref = (
                tuple(tuple(row) for row in rb_regions),
                tuple(
                    s if s == C.REGION_OPEN else (rb_control[r] + 1) * 10 + s
                    for r, s in enumerate(rb_states)
                ),
            )

    recent = [-1] * C.NUM_FACTIONS  # derived (R-303)
    for k in range(1, struggles + 1):
        r = slots[k - 1]
        if states[r] == C.REGION_CONTROLLED:
            recent[control[r]] = k

    return {
        "region_states": states,
        "region_control": control,
        "struggles_resolved": struggles,
        "negotiation_discs": neg,
        "hands": hand_list,
        "pass_count": pass_count,
        "to_move": to_play,
        "plays_total": total,
        "last_play": last_play,
        "hand_empty": hand_empty,
        "recent_win": recent,
        "last_card": last_card,
        "reference_board": ref,
    }


def _validate_records(
    last_play: list[Any], hand_empty: list[Any], sizes: list[int], total: int
) -> None:
    """V7."""
    played = [CARDS_PER_HAND - s for s in sizes]
    vals = [v for v in last_play if v is not None]
    if len(set(vals)) != len(vals) or any(
        not isinstance(v, int) or not 1 <= v <= total for v in vals
    ):
        raise _fail("V7", "last_play values must be distinct integers in 1..total")
    for p, v in enumerate(last_play):
        if (v is None) != (played[p] == 0) or (v is not None and v < played[p]):
            raise _fail("V7", f"last_play[{p}] inconsistent with cards played")
    if total and max(vals) != total:
        raise _fail("V7", "largest last_play must equal the card-play total")
    for p, v in enumerate(hand_empty):
        if (v is not None) != (sizes[p] == 0) or (v is not None and v != last_play[p]):
            raise _fail("V7", f"hand_empty[{p}] inconsistent")
