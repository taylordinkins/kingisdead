"""Invariant checker for random-simulation tests (Phase 2 unit 11).

``check_invariants(state)`` raises ``InvariantViolation`` naming the invariant and rule ID on the
first violation. State attributes may be lists, tuples, numpy arrays or dicts.
"""

from typing import Any

from kingisdead import constants as C


class InvariantViolation(AssertionError):
    """A game-state invariant (docs/RULES_SPEC.md) does not hold."""


def _fail(rule: str, name: str, detail: str) -> None:
    raise InvariantViolation(f"{rule} {name}: {detail}")


def _ints(x: Any) -> list[int]:
    return [int(v) for v in x]


def _hand(h: Any) -> dict[int, int]:
    if hasattr(h, "items"):
        return {int(k): int(v) for k, v in h.items()}
    vals = _ints(h)
    off = 0 if len(vals) > max(C.STARTING_HAND) else 1
    return {i + off: v for i, v in enumerate(vals)}


def check_invariants(state: Any) -> None:
    """Raise InvariantViolation on the first violated invariant. Implements R-015 and friends."""
    s = state
    n = len(s.courts)
    nf, nr = C.NUM_FACTIONS, C.NUM_REGIONS
    pool = C.FOLLOWERS_PER_FACTION[n]
    counts = [_ints(r) for r in s.region_counts]
    courts = [_ints(c) for c in s.courts]
    supply = _ints(s.supply)
    rstates = _ints(s.region_states)
    ctrl = [-1 if c is None else int(c) for c in s.region_control]
    resolved = int(s.struggles_resolved)
    terminal = bool(s.is_terminal())
    setup_done = s.stage == C.STAGE_DONE

    # R-005 / R-015 conservation.
    if len(counts) != nr or len(rstates) != nr or len(ctrl) != nr:
        _fail("R-001", "region arrays", f"expected {nr} regions")
    for f in range(nf):
        vals = [r[f] for r in counts] + [c[f] for c in courts] + [supply[f]]
        if min(vals) < 0:
            _fail("R-005", "non-negative followers", f"faction {f} has negative count {vals}")
        total = sum(vals)
        if total != pool:
            _fail("R-015", "follower conservation", f"faction {f} has {total}, pool is {pool}")

    # R-004 / R-006 region states.
    for r in range(nr):
        st = rstates[r]
        if st not in (C.REGION_OPEN, C.REGION_CONTROLLED, C.REGION_UNSTABLE):
            _fail("R-004", "region state", f"region {r} has unknown state {st}")
        if st == C.REGION_CONTROLLED and not 0 <= ctrl[r] < nf:
            _fail("R-004", "controlled region has controller", f"region {r} control {ctrl[r]}")
        if st != C.REGION_CONTROLLED and ctrl[r] != -1:
            _fail("R-004", "only controlled regions have a controller", f"region {r}")
        if st != C.REGION_OPEN and any(counts[r]):
            _fail("R-015", "no followers on closed regions", f"region {r} holds {counts[r]}")
    unstable = rstates.count(C.REGION_UNSTABLE)
    if unstable > C.INSTABILITY_DISCS:
        _fail("R-006", "instability discs", f"{unstable} unstable regions")
    if unstable == C.INSTABILITY_DISCS and not terminal:
        _fail("R-304", "third instability disc ends the game", "non-terminal with 3 unstable")
    for f in range(nf):
        k = sum(1 for r in range(nr) if rstates[r] == C.REGION_CONTROLLED and ctrl[r] == f)
        if k > C.CONTROL_DISCS_PER_FACTION:
            _fail("R-006", "control discs", f"faction {f} controls {k}")

    # R-010 / R-300..R-303 slots and struggles.
    if resolved < 0 or resolved > nr:
        _fail("R-303", "struggles_resolved range", f"{resolved}")
    if setup_done:
        slots = [None if v is None else int(v) for v in s.slot_regions]
        if sorted(v if v is not None else -1 for v in slots) != list(range(nr)):
            _fail("R-010", "slot_regions permutation", f"{slots}")
        closed = {r for r in range(nr) if rstates[r] != C.REGION_OPEN}
        if set(slots[:resolved]) != closed or len(closed) != resolved:
            _fail(
                "R-303",
                "slots 1..struggles_resolved are the closed regions",
                f"resolved={resolved} slots={slots} closed={sorted(closed)}",
            )

    # R-008 / R-102 hands.
    hands = [_hand(h) for h in s.hands]
    played = 0
    for p, h in enumerate(hands):
        for card, k in h.items():
            if k < 0:
                _fail("R-008", "hand counts", f"player {p} card {card} has {k}")
            if k > C.STARTING_HAND.get(card, 0):
                _fail("R-008", "starting hand limit", f"player {p} has {k} of card {card}")
        size = sum(h.values())
        if size > 8:
            _fail("R-008", "hand size", f"player {p} has {size} cards")
        played += 8 - size
    if setup_done and int(s.plays_total) != played:
        _fail("R-102", "plays_total", f"plays_total={s.plays_total}, hands imply {played}")

    # R-006 negotiation discs.
    discs = [None if d is None else int(d) for d in s.negotiation_discs]
    if len(discs) != n:
        _fail("R-006", "one negotiation disc per player", f"{len(discs)} discs for {n} players")
    placed = [d for d in discs if d is not None and d >= 0]
    if any(d >= nr for d in placed):
        _fail("R-006", "disc region", f"{discs}")
    if len(set(placed)) != len(placed):
        _fail("R-006", "discs on distinct regions", f"{discs}")

    # R-103 pass count.
    pc = int(s.pass_count)
    if not 0 <= pc <= n - 1:
        _fail("R-103", "pass_count", f"{pc} with {n} players")

    # R-303 recent wins.
    wins = [w for w in _ints(s.recent_win) if w != -1]
    if any(w < 1 or w > resolved for w in wins):
        _fail("R-303", "recent_win range", f"{list(s.recent_win)} resolved={resolved}")
    if len(set(wins)) != len(wins):
        _fail("R-303", "recent_win distinct", f"{list(s.recent_win)}")

    # R-304 / R-405 / R-101 node level.
    rets = [float(v) for v in s.returns()]
    if terminal:
        if abs(sum(rets)) > 1e-9:
            _fail("R-405", "returns sum to 0", f"{rets}")
        if list(s.legal_actions()):
            _fail("R-304", "terminal has no legal actions", "")
    else:
        if any(abs(v) > 1e-9 for v in rets):
            _fail("R-405", "returns zero before the end", f"{rets}")
        if not s.is_chance_node() and not list(s.legal_actions()):
            _fail("R-101", "decision node has legal actions", "")
