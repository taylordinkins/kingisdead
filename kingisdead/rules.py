"""Pure rule helpers (no pyspiel, no I/O, no randomness). Implements R-200..R-213 helpers."""

from __future__ import annotations

from collections.abc import Sequence

from kingisdead import constants as C

# Support card id -> faction (ACTIONS.md section 2: 1 Scottish, 2 Welsh, 3 English).
SUPPORT_FACTION = {1: 0, 2: 1, 3: 2}
SUPPORT_PLACED = 2


def support_eligible_regions(
    faction: int, region_states: Sequence[int], region_control: Sequence[int]
) -> list[int]:
    """Implements R-210 (and R-200): open regions bordering a region controlled by `faction`, or
    bordering the faction's open home region."""
    home = C.HOME_REGION[faction]
    home_open = region_states[home] == C.REGION_OPEN
    out: list[int] = []
    for r in range(C.NUM_REGIONS):
        if region_states[r] != C.REGION_OPEN:
            continue
        adj = C.ADJACENCY[r]
        via_control = any(
            region_states[n] == C.REGION_CONTROLLED and region_control[n] == faction for n in adj
        )
        if via_control or (home_open and home in adj):
            out.append(r)
    return out


def support_count(supply: int) -> int:
    """Implements R-211: followers placed by a Support card."""
    return min(SUPPORT_PLACED, supply)


def summon_options(region_counts: Sequence[Sequence[int]]) -> list[tuple[int, int]]:
    """Implements R-201: every (region, faction) pair present on the board."""
    return [
        (r, f)
        for r in range(C.NUM_REGIONS)
        for f in range(C.NUM_FACTIONS)
        if region_counts[r][f] > 0
    ]


def next_assemble_faction(supply: Sequence[int], after: int) -> int | None:
    """Implements R-212: the next faction (S, W, E order) after `after` with followers in supply."""
    for f in range(after + 1, C.NUM_FACTIONS):
        if supply[f] > 0:
            return f
    return None


def negotiate_eligible(
    slot_regions: Sequence[int | None], struggles: int, discs: Sequence[int | None]
) -> list[int]:
    """Implements R-213: face-up regions (slots after the resolved struggles) with no disc."""
    return sorted(r for r in slot_regions[struggles:] if r is not None and r not in discs)


def negotiate_first_options(eligible: Sequence[int]) -> list[int]:
    """Implements R-213: eligible regions with an eligible partner of higher region index."""
    return [r for r in eligible if any(o > r for o in eligible)]


def negotiate_swap(slot_regions: Sequence[int | None], a: int, b: int) -> list[int | None]:
    """Implements R-213: exchange the slots of the cards of regions a and b."""
    out = list(slot_regions)
    ia, ib = out.index(a), out.index(b)
    out[ia], out[ib] = b, a
    return out
