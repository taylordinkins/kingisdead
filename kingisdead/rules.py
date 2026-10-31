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


# -- Manoeuvre / Outmanoeuvre (R-214..R-217) ---------------------------------------------------
Board = tuple[tuple[int, ...], ...]
Picks = tuple[tuple[int, int], ...]  # FOLLOWER(r, f) picks, in action order
MANOEUVRE = 6  # card ids (ACTIONS.md section 2)
OUTMANOEUVRE = 7
MODE_NONE = 0
MODE_ONE_FOR_TWO = 1
MODE_ONE_FOR_ONE = 2
MODE_MANOEUVRE = 3


def board_of(region_counts: Sequence[Sequence[int]]) -> Board:
    """Immutable copy of the followers per region and faction."""
    return tuple(tuple(row) for row in region_counts)


def state_signature(region_states: Sequence[int], region_control: Sequence[int]) -> tuple[int, ...]:
    """Implements R-216: each region's state (R-004) including the controlling faction."""
    return tuple(
        s if s == C.REGION_OPEN else (region_control[r] + 1) * 10 + s
        for r, s in enumerate(region_states)
    )


def apply_swap(board: Board, mode: int, picks: Picks) -> Board:
    """Implements R-214/R-215: the board after a swap given by complete `picks`.

    MODE_MANOEUVRE and MODE_ONE_FOR_ONE: picks = ((r1, f1), (r2, f2)).
    MODE_ONE_FOR_TWO: picks = ((r1, fx), (r2, fy), (r2, fz)); the single goes to r2, the pair to r1.
    """
    rows = [list(row) for row in board]
    (r1, f1), (r2, f2) = picks[0], picks[1]
    rows[r1][f1] -= 1
    rows[r2][f1] += 1
    rows[r2][f2] -= 1
    rows[r1][f2] += 1
    if mode == MODE_ONE_FOR_TWO:
        f3 = picks[2][1]
        rows[r2][f3] -= 1
        rows[r1][f3] += 1
    return tuple(tuple(row) for row in rows)


def swap_candidates(board: Board, mode: int, block: Board | None) -> list[Picks]:
    """Implements R-214, R-215, R-216: every legal complete pick sequence in canonical order.

    A swap is legal if its result differs from the blocked board `block` (None: nothing blocked).
    """
    nf = C.NUM_FACTIONS
    out: list[Picks] = []
    if mode == MODE_ONE_FOR_TWO:
        for r1 in range(C.NUM_REGIONS):
            for fx in range(nf):
                if board[r1][fx] == 0:
                    continue
                for r2 in C.ADJACENCY[r1]:
                    for fy in range(nf):
                        for fz in range(fy, nf):
                            if board[r2][fy] < (2 if fy == fz else 1) or board[r2][fz] < 1:
                                continue
                            picks = ((r1, fx), (r2, fy), (r2, fz))
                            if apply_swap(board, mode, picks) != block:
                                out.append(picks)
        return out
    for r1 in range(C.NUM_REGIONS):
        for f1 in range(nf):
            if board[r1][f1] == 0:
                continue
            others = range(r1 + 1, C.NUM_REGIONS) if mode == MODE_MANOEUVRE else C.ADJACENCY[r1]
            for r2 in others:
                if r2 <= r1:
                    continue
                for f2 in range(nf):
                    if board[r2][f2] == 0:
                        continue
                    picks = ((r1, f1), (r2, f2))
                    if apply_swap(board, mode, picks) != block:
                        out.append(picks)
    return out


def swap_mode(card: int, board: Board, block: Board | None) -> int:
    """Implements R-214/R-215: the form used when the card is played (MODE_NONE: no effect)."""
    if card == MANOEUVRE:
        return MODE_MANOEUVRE if swap_candidates(board, MODE_MANOEUVRE, block) else MODE_NONE
    for mode in (MODE_ONE_FOR_TWO, MODE_ONE_FOR_ONE):
        if swap_candidates(board, mode, block):
            return mode
    return MODE_NONE


def swap_next_picks(
    board: Board, mode: int, block: Board | None, prefix: Picks
) -> list[tuple[int, int]]:
    """Implements R-214, R-215, R-216: legal next FOLLOWER picks after `prefix`."""
    n = len(prefix)
    out: list[tuple[int, int]] = []
    for cand in swap_candidates(board, mode, block):
        if cand[:n] == prefix and cand[n] not in out:
            out.append(cand[n])
    return out


def swap_length(mode: int) -> int:
    """Number of FOLLOWER picks of a swap in `mode`."""
    return 3 if mode == MODE_ONE_FOR_TWO else 2


# -- Power struggle (R-300..R-304) -------------------------------------------------------------
def struggle_winner(counts: Sequence[int]) -> int | None:
    """Implements R-301: the faction with strictly the most followers, else None (unstable)."""
    best = max(counts)
    if best <= 0 or list(counts).count(best) > 1:
        return None
    return list(counts).index(best)


def game_over(region_states: Sequence[int], struggles: int) -> bool:
    """Implements R-304: three instability discs placed, or the eighth struggle resolved."""
    unstable = sum(1 for s in region_states if s == C.REGION_UNSTABLE)
    return unstable >= C.INSTABILITY_DISCS or struggles >= C.NUM_REGIONS


# -- Game end and scoring (R-400..R-405) -------------------------------------------------------
def is_invasion(region_states: Sequence[int]) -> bool:
    """Implements R-304/R-400: three instability discs are on the board (checked first)."""
    return sum(1 for s in region_states if s == C.REGION_UNSTABLE) >= C.INSTABILITY_DISCS


def complete_sets(court: Sequence[int]) -> int:
    """Implements R-402: minimum over the factions of the follower count in the court."""
    return min(court)


def _best_record(tied: list[int], key: Sequence[int | None], best: str) -> list[int]:
    """Players among `tied` with the best record; None (never) loses; all if nobody has one."""
    have = [p for p in tied if key[p] is not None]
    if not have:
        return tied
    values = [v for v in (key[p] for p in have) if v is not None]
    target = max(values) if best == "max" else min(values)
    return [p for p in have if key[p] == target]


def _most(tied: list[int], values: Sequence[int]) -> list[int]:
    top = max(values[p] for p in tied)
    return [p for p in tied if values[p] == top]


def invasion_winners(courts: Sequence[Sequence[int]], last_play: Sequence[int | None]) -> list[int]:
    """Implements R-402: most complete sets, then highest last-play number; all share if none."""
    tied = _most(list(range(len(courts))), [complete_sets(c) for c in courts])
    return _best_record(tied, last_play, "max")


def coronation_ranking(
    region_states: Sequence[int], region_control: Sequence[int], recent_win: Sequence[int]
) -> list[int | None]:
    """Implements R-403: factions by regions controlled then recent-win, both descending.

    Returns [rank 1, rank 2, rank 3]; a rank is None where tied factions leave it undefined.
    """
    nf = C.NUM_FACTIONS
    keys = [
        (
            sum(
                1
                for r, s in enumerate(region_states)
                if s == C.REGION_CONTROLLED and region_control[r] == f
            ),
            recent_win[f],
        )
        for f in range(nf)
    ]
    order = sorted(range(nf), key=lambda f: keys[f], reverse=True)
    return [None if any(keys[g] == keys[f] for g in order if g != f) else f for f in order]


def coronation_winners(
    courts: Sequence[Sequence[int]],
    ranking: Sequence[int | None],
    hand_empty: Sequence[int | None],
) -> list[int]:
    """Implements R-404: rank-1 followers, then rank-2 (if defined), then earliest empty hand."""
    tied = list(range(len(courts)))
    for f in ranking[:2]:
        if f is not None and len(tied) > 1:
            tied = _most(tied, [c[f] for c in courts])
    if len(tied) > 1:
        tied = _best_record(tied, hand_empty, "min")
    return tied


def game_returns(n: int, winners: Sequence[int]) -> list[float]:
    """Implements R-405: k winners of n get (n-k)/(k(n-1)), the others -1/(n-1)."""
    k = len(winners)
    win = (n - k) / (k * (n - 1))
    return [win if p in winners else -1.0 / (n - 1) for p in range(n)]
