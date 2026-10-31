"""Action and chance-outcome encoding (docs/ACTIONS.md sections 1-3, R-007)."""

from typing import Literal, NamedTuple

from kingisdead.constants import CARD_NAMES, FACTION_NAMES, NUM_FACTIONS, NUM_REGIONS

NUM_CARDS = len(CARD_NAMES)
PASS = 0
PLAY_BASE = 1
REGION_BASE = PLAY_BASE + NUM_CARDS
FOLLOWER_BASE = REGION_BASE + NUM_REGIONS
NUM_DISTINCT_ACTIONS = FOLLOWER_BASE + NUM_REGIONS * NUM_FACTIONS
MAX_CHANCE_OUTCOMES = NUM_REGIONS


class Decoded(NamedTuple):
    kind: Literal["PASS", "PLAY", "REGION", "FOLLOWER"]
    card: int | None = None
    region: int | None = None
    faction: int | None = None


def _check(value: int, lo: int, hi: int, what: str) -> int:
    if not lo <= value < hi:
        raise ValueError(f"{what} {value} out of range {lo}..{hi - 1}")
    return value


def play_action(card: int) -> int:
    _check(card, 1, NUM_CARDS + 1, "card")
    return card


def region_action(r: int) -> int:
    return REGION_BASE + _check(r, 0, NUM_REGIONS, "region")


def follower_action(r: int, f: int) -> int:
    _check(r, 0, NUM_REGIONS, "region")
    _check(f, 0, NUM_FACTIONS, "faction")
    return FOLLOWER_BASE + NUM_FACTIONS * r + f


def decode_action(action: int) -> Decoded:
    _check(action, 0, NUM_DISTINCT_ACTIONS, "action")
    if action == PASS:
        return Decoded("PASS")
    if action < REGION_BASE:
        return Decoded("PLAY", card=action)
    if action < FOLLOWER_BASE:
        return Decoded("REGION", region=action - REGION_BASE)
    r, f = divmod(action - FOLLOWER_BASE, NUM_FACTIONS)
    return Decoded("FOLLOWER", region=r, faction=f)


def action_label(action: int) -> str:
    from kingisdead.constants import REGION_NAMES

    d = decode_action(action)
    if d.kind == "PASS":
        return "Pass"
    if d.kind == "PLAY":
        return f"Play {CARD_NAMES[d.card]}"  # type: ignore[index]
    if d.kind == "REGION":
        return f"Region {REGION_NAMES[d.region]}"  # type: ignore[index]
    return f"{FACTION_NAMES[d.faction]} follower in {REGION_NAMES[d.region]}"  # type: ignore[index]


def _chance_limit(kind: str) -> int:
    if kind == "region":
        return NUM_REGIONS
    if kind == "faction":
        return NUM_FACTIONS
    raise ValueError(f"unknown chance kind {kind!r}")


def decode_chance_outcome(outcome: int, kind: str) -> int:
    return _check(outcome, 0, _chance_limit(kind), f"{kind} outcome")


def encode_chance_outcome(value: int, kind: str) -> int:
    return _check(value, 0, _chance_limit(kind), f"{kind} value")
