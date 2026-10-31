"""Pure rule helpers (no pyspiel, no I/O, no randomness). Implements R-200, R-201, R-210, R-211."""

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
