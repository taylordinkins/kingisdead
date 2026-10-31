"""Acceptance tests for Manoeuvre, Outmanoeuvre and the undo block: R-214, R-215, R-216, R-217
(Phase 2 unit 7), with R-200/R-201/R-202 interactions.

Assumed identifiers (same as test_support_summon.py / test_assemble_negotiate.py):
  s.region_counts[r][f], s.courts[p][f], s.supply[f], s.hands[p] (card id -> copies),
  s.pass_count; legal_actions(), current_player(), apply_action(), clone();
  ``kingisdead.scenario.load_scenario(dict_or_path)``. B* is NOT read from the state: it is
  observed only through the legal-action masks, and positions with a given B* are made through the
  scenario ``last_card.reference_board`` field (SCENARIOS.md).
The phase is inferred from legal_actions() and the number of picks made: every pick of these cards
is a FOLLOWER(r, f) = 16 + 3r + f action; the SUMMON mask is the set of present (region, faction).
PLAY(6) = Manoeuvre, PLAY(7) = Outmanoeuvre, REGION(r) = 8 + r.

The expected masks are computed by an independent brute-force oracle written here from
R-002, R-214, R-215, R-216 and ACTIONS.md sections 4-5 (see ``_man_seqs`` / ``_out_seqs``). Tests
walk the engine's whole decision tree after PLAY and compare the set of action sequences, the
mask at each node and the resulting board with the oracle's. Because the oracle lists each swap
once in canonical order, equality of the sets also checks canonical-ordering uniqueness.
"""

import copy
import json
from pathlib import Path

import pytest

SCEN = Path(__file__).resolve().parent.parent / "scenarios"
REGIONS = [
    "Moray",
    "Strathclyde",
    "Lancaster",
    "Northumbria",
    "Gwynedd",
    "Warwick",
    "Essex",
    "Devon",
]
ADJ = {
    0: {1},
    1: {0, 2, 3},
    2: {1, 3, 4, 5},
    3: {1, 2, 5, 6},
    4: {2, 5, 7},
    5: {2, 3, 4, 6, 7},
    6: {3, 5, 7},
    7: {4, 5, 6},
}
FN = ["S", "W", "E"]
POOL = {2: 16, 3: 18}
CARD_NAMES = {6: "manoeuvre", 7: "outmanoeuvre", 4: "assemble"}
FULL_HAND = [
    "scottish_support",
    "welsh_support",
    "english_support",
    "assemble",
    "assemble",
    "negotiate",
    "manoeuvre",
    "outmanoeuvre",
]
MAN, OUT = 6, 7
S, W, E = 0, 1, 2


def F(r, f):
    return 16 + 3 * r + f


def region(r):
    return 8 + r


# ---------------------------------------------------------------- state building


def _pos(
    board,
    *,
    players=2,
    closed=None,
    last=None,
    ref=None,
    ref_closed=None,
    to_play=None,
    courts=None,
    supply=None,
):
    """State from a scenario. ``board``: {region: {faction: n}} on open regions; ``closed``:
    ordered {region: 'S'|'W'|'E'|'unstable'} taking slots 1..k (V4); ``last``: card name of the
    most recent play, made by seat 0 as the only card play (then seat 1 acts unless ``to_play``);
    ``ref``: B* as {region: {faction: n}} (only with last manoeuvre/outmanoeuvre; omitted means
    void); ``ref_closed`` defaults to ``closed``; ``courts``: list of {faction: n} for the first
    seats; ``supply``: {faction: n}, default 0 each. The remainder of each pool goes to the last
    seat's court."""
    from kingisdead.scenario import load_scenario

    closed = closed or {}
    courts = list(courts or [])
    courts += [{} for _ in range(players - len(courts))]
    supply = {0: 0, 1: 0, 2: 0, **(supply or {})}
    court_last = {}
    for f in range(3):
        used = (
            sum(c.get(f, 0) for c in board.values())
            + sum(c.get(f, 0) for c in courts[:-1])
            + courts[-1].get(f, 0)
            + supply[f]
        )
        rest = POOL[players] - used
        assert rest >= 0
        if rest:
            court_last[f] = courts[-1].get(f, 0) + rest
        elif courts[-1].get(f, 0):
            court_last[f] = courts[-1][f]
    courts[-1] = court_last
    slots = list(closed) + [r for r in range(8) if r not in closed]

    def cm(c):
        return {FN[f]: n for f, n in c.items() if n}

    hands = [list(FULL_HAND) for _ in range(players)]
    data = {
        "format": 1,
        "kind": "state",
        "players": players,
        "slots": [REGIONS[r] for r in slots],
        "regions": {REGIONS[r]: cm(c) for r, c in board.items() if cm(c)},
        "courts": [cm(c) for c in courts],
        "to_play": 0 if to_play is None else to_play,
        "struggles": len(closed),
        "region_state": {REGIONS[r]: v for r, v in closed.items()},
        "hands": hands,
    }
    if last is not None:
        hands[0].remove(last)
        data["last_play"] = [1] + [None] * (players - 1)
        data["last_card"] = {"type": last}
        if to_play is None:
            data["to_play"] = 1
        if ref is not None:
            rc = closed if ref_closed is None else ref_closed
            data["last_card"]["reference_board"] = {
                "regions": {REGIONS[r]: cm(c) for r, c in ref.items() if cm(c)},
                "region_state": {REGIONS[r]: v for r, v in rc.items()},
            }
    return load_scenario(copy.deepcopy(data))


def _counts(s):
    return [list(map(int, row)) for row in s.region_counts]


def _tb(board):
    """Normalise {region: {faction: n}} to the oracle's tuple-of-tuples board."""
    return tuple(tuple(board.get(r, {}).get(f, 0) for f in range(3)) for r in range(8))


def _tc(s):
    return tuple(tuple(row) for row in _counts(s))


def _conserved(s, players=2):
    c = _counts(s)
    for f in range(3):
        total = (
            sum(row[f] for row in c)
            + sum(int(s.courts[p][f]) for p in range(players))
            + int(s.supply[f])
        )
        assert total == POOL[players], f"faction {f}: {total}"


def _present(counts):
    return sorted(F(r, f) for r, row in enumerate(counts) for f, n in enumerate(row) if n > 0)


def _hand(s, p):
    return {c: n for c, n in dict(s.hands[p]).items() if n}


# ---------------------------------------------------------------- oracle


def _mutate(b, ops):
    rows = [list(row) for row in b]
    for r, f, d in ops:
        rows[r][f] += d
    return tuple(tuple(row) for row in rows)


def _man_seqs(b, bstar):
    """R-214/R-216: {(F(r1,f1), F(r2,f2)): result} with r1 < r2, result != B*."""
    items = [(r, f) for r in range(8) for f in range(3) if b[r][f] > 0]
    out = {}
    for r1, f1 in items:
        for r2, f2 in items:
            if r2 > r1:
                res = _mutate(b, [(r1, f1, -1), (r2, f1, 1), (r2, f2, -1), (r1, f2, 1)])
                if res != bstar:
                    out[(F(r1, f1), F(r2, f2))] = res
    return out


def _out_seqs(b, bstar):
    """R-215/R-216: (depth, {sequence: result}); mode fixed by the position."""
    two = {}
    for r1 in range(8):
        for fx in range(3):
            if b[r1][fx] == 0:
                continue
            for r2 in ADJ[r1]:
                for fy in range(3):
                    for fz in range(fy, 3):
                        need = 2 if fy == fz else 1
                        if b[r2][fy] < need or (fy != fz and b[r2][fz] < 1):
                            continue
                        res = _mutate(
                            b,
                            [
                                (r1, fx, -1),
                                (r2, fy, -1),
                                (r2, fz, -1),
                                (r1, fy, 1),
                                (r1, fz, 1),
                                (r2, fx, 1),
                            ],
                        )
                        if res != bstar:
                            two[(F(r1, fx), F(r2, fy), F(r2, fz))] = res
    if two:
        return 3, two
    one = {}
    for r1 in range(8):
        for f1 in range(3):
            if b[r1][f1] == 0:
                continue
            for r2 in ADJ[r1]:
                if r2 <= r1:
                    continue
                for f2 in range(3):
                    if b[r2][f2] == 0:
                        continue
                    res = _mutate(b, [(r1, f1, -1), (r2, f1, 1), (r2, f2, -1), (r1, f2, 1)])
                    if res != bstar:
                        one[(F(r1, f1), F(r2, f2))] = res
    if one:
        return 2, one
    return 0, {(): b}


def _oracle(card, b, bstar):
    if card == MAN:
        seqs = _man_seqs(b, bstar)
        return (2, seqs) if seqs else (0, {(): b})
    return _out_seqs(b, bstar)


def _explore(s, card, depth, players=2):
    """Play ``card`` and walk every action sequence of ``depth`` picks. Returns
    {sequence: board after the picks}; checks masks are FOLLOWER ids without duplicates, the
    acting player is unchanged, followers are conserved and each leaf is at the SUMMON step."""
    me = s.current_player()
    out = {}

    def rec(st, prefix):
        _conserved(st, players)
        if len(prefix) == depth:
            out[tuple(prefix)] = _tc(st)
            legal = st.legal_actions()
            present = _present(_counts(st))
            if present:
                assert st.current_player() == me
                assert legal == present, "SUMMON mask must be the present (region, faction) pairs"
            else:
                assert st.current_player() != me
            return
        assert st.current_player() == me
        legal = st.legal_actions()
        assert legal, f"dead end after {prefix}"
        assert len(set(legal)) == len(legal)
        assert all(a >= 16 for a in legal)
        for a in legal:
            t = st.clone()
            t.apply_action(a)
            rec(t, prefix + [a])

    t = s.clone()
    t.apply_action(card)
    rec(t, [])
    return out


def _check(s, card, bstar, players=2):
    """Compare the engine's decision tree for ``card`` with the oracle's."""
    b = _tc(s)
    depth, expected = _oracle(card, b, bstar)
    got = _explore(s, card, depth, players)
    assert set(got) == set(expected)
    for seq, res in expected.items():
        assert got[seq] == res, f"result of {seq}"
    return depth, expected


BOARDS = {
    "pure": ({0: {S: 4}, 6: {E: 4}}, {}),
    "mixed3": ({0: {S: 1}, 1: {W: 2}, 7: {E: 1}}, {}),
    "dense": ({0: {S: 1, E: 1}, 1: {S: 1, W: 1, E: 1}, 7: {W: 4}}, {}),
    "all_single": ({r: {S: 1, W: 1, E: 1} for r in range(8)}, {}),
    "mid": ({2: {S: 2, W: 1}, 3: {W: 2, E: 1}, 5: {S: 1, E: 3}, 4: {W: 1}}, {}),
    "closed": ({1: {W: 2}, 2: {E: 1, S: 1}, 4: {S: 3}, 6: {E: 2}}, {0: "S", 5: "unstable"}),
    "one_region": ({3: {S: 3}}, {}),
    "empty": ({}, {}),
    "two_apart": ({0: {S: 1}, 2: {E: 1}}, {}),
}


def _ref_candidates(card, b):
    """B* candidates: a few results of legal swaps, plus the board itself (no-op swaps)."""
    if card == MAN:
        res = sorted({v for v in _man_seqs(b, None).values()})
    else:
        res = sorted({v for v in _out_seqs(b, None)[1].values()})
    pick = []
    if res:
        pick = sorted({res[0], res[len(res) // 2], res[-1]})
    if b not in pick:
        pick.append(b)
    return pick


def _bd(t):
    return {r: {f: n for f, n in enumerate(row) if n} for r, row in enumerate(t) if any(row)}


# ================================================================ R-214 Manoeuvre


def test_R214_example_swap_moray_essex():
    """R-214 example: Moray [S S S S], Essex [E E E E]: swapping (Moray,S) with (Essex,E) gives
    Moray [S S S E], Essex [E E E S]. MAN_FIRST offers only the lower region's follower."""
    s = _pos({0: {S: 4}, 6: {E: 4}})
    s.apply_action(MAN)
    assert s.legal_actions() == [F(0, S)]
    s.apply_action(F(0, S))
    assert s.legal_actions() == [F(6, E)]
    s.apply_action(F(6, E))
    assert _counts(s)[0] == [3, 0, 1]
    assert _counts(s)[6] == [1, 0, 3]
    _conserved(s)
    assert s.current_player() == 0
    assert s.legal_actions() == _present(_counts(s))


def test_R214_second_pick_requires_higher_region():
    """R-214 / ACTIONS MAN_SECOND: after (r1,f1) only followers on regions r2 > r1 are offered
    (the lower region goes first; the swap has exactly one sequence)."""
    s = _pos({1: {S: 1, W: 1}, 3: {E: 1}, 5: {S: 1}})
    s.apply_action(MAN)
    # r1 = 1 or 3 (5 has no higher region with followers)
    assert s.legal_actions() == [F(1, S), F(1, W), F(3, E)]
    s.apply_action(F(3, E))
    assert s.legal_actions() == [F(5, S)]
    t = s.clone()
    t.apply_action(F(5, S))
    s2 = _pos({1: {S: 1, W: 1}, 3: {E: 1}, 5: {S: 1}})
    s2.apply_action(MAN)
    s2.apply_action(F(1, W))
    assert s2.legal_actions() == [F(3, E), F(5, S)]


def test_R214_same_faction_swap_is_legal_noop():
    """R-214: f1 may equal f2; the board is unchanged but the card is played (no undo block
    is active here)."""
    s = _pos({0: {S: 2}, 6: {S: 2}})
    s.apply_action(MAN)
    assert s.legal_actions() == [F(0, S)]
    s.apply_action(F(0, S))
    assert s.legal_actions() == [F(6, S)]
    s.apply_action(F(6, S))
    assert _counts(s)[0] == [2, 0, 0] and _counts(s)[6] == [2, 0, 0]
    assert _hand(s, 0).get(MAN, 0) == 0


def test_R214_only_two_followers_each_one_swap():
    """R-214: with exactly one follower in each of two regions the single swap is forced, and it
    exchanges them: Moray [S], Devon [E] gives Moray [E], Devon [S]."""
    s = _pos({0: {S: 1}, 7: {E: 1}})
    for a in (MAN, F(0, S), F(7, E)):
        s.apply_action(a)
    assert _counts(s)[0] == [0, 0, 1] and _counts(s)[7] == [1, 0, 0]
    _conserved(s)


def test_R214_closed_regions_never_involved():
    """R-214 / R-200: closed regions hold no followers and no pick or result involves them."""
    s = _pos({2: {S: 1}, 3: {W: 1}, 4: {E: 1}}, closed={0: "S", 1: "unstable"})
    s.apply_action(MAN)
    assert all(a >= F(2, S) for a in s.legal_actions())
    for a in s.legal_actions():
        t = s.clone()
        t.apply_action(a)
        for b in t.legal_actions():
            u = t.clone()
            u.apply_action(b)
            assert _counts(u)[0] == [0, 0, 0] and _counts(u)[1] == [0, 0, 0]


def test_R214_no_legal_swap_goes_to_summon():
    """R-214 / R-202: followers in a single region: no swap exists, so PLAY(6) has no sub-steps;
    the card is spent, the board is unchanged and play goes straight to SUMMON."""
    s = _pos({3: {S: 2, W: 1}})
    s.apply_action(MAN)
    assert s.current_player() == 0
    assert s.legal_actions() == [F(3, S), F(3, W)]
    assert _counts(s)[3] == [2, 1, 0]
    assert _hand(s, 0).get(MAN, 0) == 0
    s.apply_action(F(3, W))
    assert s.current_player() == 1
    _conserved(s)


def test_R214_no_followers_at_all_skips_summon():
    """R-214 / R-202 / R-201: empty board: no effect and no summon; the turn passes on."""
    s = _pos({})
    s.apply_action(MAN)
    assert s.current_player() == 1
    assert 0 in s.legal_actions()
    assert _hand(s, 0).get(MAN, 0) == 0


def test_R214_play_bookkeeping():
    """R-102 with R-214: after Manoeuvre and summon the hand has 7 cards, the pass count is 0 and
    the next seat acts."""
    s = _pos({0: {S: 4}, 6: {E: 4}})
    assert s.pass_count == 0
    for a in (MAN, F(0, S), F(6, E), F(0, E)):
        s.apply_action(a)
    assert sum(_hand(s, 0).values()) == 7
    assert s.pass_count == 0
    assert s.current_player() == 1
    assert _counts(s)[0] == [3, 0, 0]
    assert int(s.courts[0][E]) == 1
    _conserved(s)


def test_R214_every_swap_has_exactly_one_sequence_count():
    """R-214 / ACTIONS section 5: with all 8 regions holding one follower of each faction there
    are C(8,2) * 3 * 3 = 252 distinct swaps and exactly 252 action sequences."""
    s = _pos(BOARDS["all_single"][0])
    seqs = _explore(s, MAN, 2)
    assert len(seqs) == 252


@pytest.mark.parametrize("name", sorted(BOARDS))
def test_R214_masks_match_oracle_no_block(name):
    """R-214 / R-202: on each board the whole Manoeuvre decision tree (masks at MAN_FIRST and
    MAN_SECOND, results, no effect when no swap exists) equals the oracle's, no B* active."""
    board, closed = BOARDS[name]
    s = _pos(board, closed=closed)
    depth, exp = _check(s, MAN, None)
    assert depth in (0, 2)


# ================================================================ R-215 Outmanoeuvre


def test_R215_example_one_for_two():
    """R-215 example: Moray [S S S S], Strathclyde [W W W W]: (Moray,S) for {W,W} gives
    Moray [S S S W W], Strathclyde [W W S]; 1-for-2 exists, so the mode is 1-for-2."""
    s = _pos({0: {S: 4}, 1: {W: 4}})
    s.apply_action(OUT)
    # OUT_SINGLE: r1/r2 are only labels for a bordering pair, so the single may be Moray's S
    # (pair {W,W}) or Strathclyde's W (pair {S,S} from Moray).
    assert sorted(s.legal_actions()) == sorted([F(0, S), F(1, W)])
    s.apply_action(F(0, S))
    assert s.legal_actions() == [F(1, W)]  # OUT_FIRST
    s.apply_action(F(1, W))
    assert s.legal_actions() == [F(1, W)]  # OUT_SECOND: second W
    s.apply_action(F(1, W))
    assert _counts(s)[0] == [3, 2, 0]
    assert _counts(s)[1] == [1, 2, 0]
    _conserved(s)
    assert s.legal_actions() == _present(_counts(s))
    assert s.current_player() == 0


def test_R215_one_for_two_forbids_one_for_one():
    """R-215 / R-202: Moray [S], Strathclyde [W W]: the 1-for-2 swap exists, so after the two
    picks (Moray,S) and (Strathclyde,W) the play is not finished - a second W is required; no
    summon is offered after a 1-for-1 pair."""
    s = _pos({0: {S: 1}, 1: {W: 2}})
    s.apply_action(OUT)
    assert s.legal_actions() == [F(0, S)]
    s.apply_action(F(0, S))
    assert s.legal_actions() == [F(1, W)]
    s.apply_action(F(1, W))
    assert s.legal_actions() == [F(1, W)]
    assert _counts(s)[1] == [0, 2, 0]  # nothing moved yet
    s.apply_action(F(1, W))
    assert _counts(s)[0] == [0, 2, 0] and _counts(s)[1] == [1, 0, 0]


def test_R215_single_region_may_be_higher_than_pair_region():
    """R-215: r1 (single) and r2 (pair) just have to border: single in Strathclyde (1), pair in
    Moray (0). Moray [W W], Strathclyde [S]: swap gives Moray [S], Strathclyde [W W]."""
    s = _pos({0: {W: 2}, 1: {S: 1}})
    s.apply_action(OUT)
    assert s.legal_actions() == [F(1, S)]
    for a in (F(1, S), F(0, W), F(0, W)):
        s.apply_action(a)
    assert _counts(s)[0] == [1, 0, 0] and _counts(s)[1] == [0, 2, 0]


def test_R215_pair_canonical_faction_order():
    """R-215 / ACTIONS OUT_SECOND: Moray [S], Strathclyde [W E]: the pair {W,E} is entered in
    faction order only. OUT_FIRST offers (Strathclyde,W) but not (Strathclyde,E) (no f' >= E left
    to pair with); OUT_SECOND after W offers E only."""
    s = _pos({0: {S: 1}, 1: {W: 1, E: 1}})
    s.apply_action(OUT)
    s.apply_action(F(0, S))
    assert s.legal_actions() == [F(1, W)]
    s.apply_action(F(1, W))
    assert s.legal_actions() == [F(1, E)]
    s.apply_action(F(1, E))
    assert _counts(s)[0] == [0, 1, 1] and _counts(s)[1] == [1, 0, 0]


def test_R215_same_faction_pair_needs_two_followers():
    """R-215 / ACTIONS OUT_SECOND: Strathclyde [W W E]: after first pick W the second may be W
    (two available) or E; after first pick E only... E needs a second E, so E is not a legal first
    pick of a pair here unless another faction >= E exists (none)."""
    s = _pos({0: {S: 1}, 1: {W: 2, E: 1}})
    s.apply_action(OUT)
    s.apply_action(F(0, S))
    assert s.legal_actions() == [F(1, W)]  # E first has no completion
    s.apply_action(F(1, W))
    assert s.legal_actions() == [F(1, W), F(1, E)]


def test_R215_non_bordering_regions_not_paired():
    """R-215 / R-002: Moray borders only Strathclyde. Moray [S S], Lancaster [W W]: Lancaster is
    not adjacent to Moray so no swap exists; the card has no effect and goes to SUMMON."""
    s = _pos({0: {S: 2}, 2: {W: 2}})
    s.apply_action(OUT)
    assert s.legal_actions() == [F(0, S), F(2, W)]
    assert _counts(s)[0] == [2, 0, 0] and _counts(s)[2] == [0, 2, 0]
    assert _hand(s, 0).get(OUT, 0) == 0


def test_R215_one_for_one_forced_when_no_region_has_two():
    """R-215 / ACTIONS 1-for-1 mode: Moray [S], Strathclyde [W], Lancaster [E] (one follower
    each): no 1-for-2 swap, so 1-for-1. OUT_SINGLE offers only followers with a bordering
    higher-region partner: (Moray,S) and (Strathclyde,W), not (Lancaster,E)."""
    s = _pos({0: {S: 1}, 1: {W: 1}, 2: {E: 1}})
    s.apply_action(OUT)
    assert s.legal_actions() == [F(0, S), F(1, W)]
    s.apply_action(F(1, W))
    assert s.legal_actions() == [F(2, E)]  # r2 must be higher and bordering
    s.apply_action(F(2, E))
    assert _counts(s)[1] == [0, 0, 1] and _counts(s)[2] == [0, 1, 0]
    assert s.legal_actions() == _present(_counts(s))
    assert s.current_player() == 0


def test_R215_one_for_one_each_swap_one_sequence():
    """R-215 / ACTIONS section 5: every region holds exactly one follower, so no region has two
    followers and no 1-for-2 swap exists. Mode is 1-for-1; each of the 13 bordering pairs gives
    exactly one sequence of two picks (lower region first)."""
    board = {r: {r % 3: 1} for r in range(8)}
    s = _pos(board)
    depth, expected = _check(s, OUT, None)
    assert depth == 2
    assert len(expected) == 13
    assert len(_explore(s, OUT, 2)) == 13


def test_R215_closed_regions_never_involved():
    """R-215 / R-200: with Moray closed, Strathclyde [W W] and Lancaster [E]: a 1-for-2 swap
    exists between the open regions and no action names the closed Moray."""
    s = _pos({1: {W: 2}, 2: {E: 1}}, closed={0: "S"})
    s.apply_action(OUT)
    assert s.legal_actions() == [F(2, E)]
    s.apply_action(F(2, E))
    assert s.legal_actions() == [F(1, W)]
    s.apply_action(F(1, W))
    s.apply_action(F(1, W))
    assert _counts(s)[0] == [0, 0, 0]
    assert _counts(s)[1] == [0, 0, 1] and _counts(s)[2] == [0, 2, 0]


def test_R215_no_effect_on_empty_board_skips_summon():
    """R-215 / R-202 / R-201: empty board: no effect, no summon, the turn passes on."""
    s = _pos({})
    s.apply_action(OUT)
    assert s.current_player() == 1
    assert _hand(s, 0).get(OUT, 0) == 0


@pytest.mark.parametrize("name", sorted(BOARDS))
def test_R215_masks_match_oracle_no_block(name):
    """R-215 / R-202: the whole Outmanoeuvre decision tree (mode, OUT_SINGLE / OUT_FIRST /
    OUT_SECOND masks, results, no effect) equals the oracle's, no B* active."""
    board, closed = BOARDS[name]
    s = _pos(board, closed=closed)
    depth, _ = _check(s, OUT, None)
    assert depth in (0, 2, 3)


# ================================================================ R-216 Undo block


@pytest.mark.parametrize("card", [MAN, OUT])
@pytest.mark.parametrize("name", sorted(BOARDS))
def test_R216_blocked_swaps_match_oracle(card, name):
    """R-216: with L the same card type and B* equal to each of several swap results (and the
    board itself, for no-op swaps), every play whose result equals B* is absent, whichever
    region is picked first and in every form; a blocked form drops out of the mode choice."""
    board, closed = BOARDS[name]
    base = _pos(board, closed=closed)
    b = _tc(base)
    for bstar in _ref_candidates(card, b):
        s = _pos(board, closed=closed, last=CARD_NAMES[card], ref=_bd(bstar))
        _check(s, card, bstar)


@pytest.mark.parametrize("card", [MAN, OUT])
def test_R216_other_card_type_not_blocked(card):
    """R-216: Manoeuvre and Outmanoeuvre do not block each other: L = the other type with a B*
    equal to a swap result leaves every swap legal."""
    board, closed = BOARDS["mixed3"]
    other = OUT if card == MAN else MAN
    base = _pos(board, closed=closed)
    b = _tc(base)
    cands = _ref_candidates(card, b)
    for bstar in cands:
        s = _pos(board, closed=closed, last=CARD_NAMES[other], ref=_bd(bstar))
        _check(s, card, None)


def test_R216_example1_reverse_swap_blocked():
    """R-216 example 1: B* = Moray [S S S S], Essex [E E E E], Devon [W W W]; now Moray [S S S E],
    Essex [E E E S], Devon [W W W]. Picking (Moray,E) with (Essex,S) is not offered; (Moray,S)
    with (Essex,E) is."""
    cur = {0: {S: 3, E: 1}, 6: {E: 3, S: 1}, 7: {W: 3}}
    ref = {0: {S: 4}, 6: {E: 4}, 7: {W: 3}}
    s = _pos(cur, last="manoeuvre", ref=ref, courts=[{W: 1}])
    s.apply_action(MAN)
    assert F(0, E) in s.legal_actions()  # has other completions
    t = s.clone()
    t.apply_action(F(0, E))
    assert F(6, S) not in t.legal_actions()
    assert F(6, E) in t.legal_actions()
    u = s.clone()
    u.apply_action(F(0, S))
    assert F(6, E) in u.legal_actions()
    _check(_pos(cur, last="manoeuvre", ref=ref, courts=[{W: 1}]), MAN, _tb(ref))


def test_R216_example1_via_real_play_and_summon():
    """R-216 example 1, end to end (3 players): seat 0 swaps (Moray,S) with (Essex,E) and summons
    a W from Devon; seat 1 then cannot pick (Moray,E) with (Essex,S)."""
    s = _pos({0: {S: 4}, 6: {E: 4}, 7: {W: 4}}, players=3, to_play=0)
    for a in (MAN, F(0, S), F(6, E), F(7, W)):
        s.apply_action(a)
    assert s.current_player() == 1
    assert _counts(s)[0] == [3, 0, 1] and _counts(s)[7] == [0, 3, 0]
    s.apply_action(MAN)
    s.apply_action(F(0, E))
    assert F(6, S) not in s.legal_actions()
    assert F(6, E) in s.legal_actions()


def test_R216_example3_other_picks_same_result_blocked():
    """R-216 example 3: Moray [E S W], Strathclyde [E S], Devon [W W W], B* = Moray [S E],
    Strathclyde [S W E], Devon [W W W]. Swapping (Strathclyde,E) for {E,W} from Moray gives B*
    and is blocked although it is not the same picks reversed: the sequence 7, (1,E), (0,W),
    (0,E) is not available."""
    cur = {0: {S: 1, W: 1, E: 1}, 1: {S: 1, E: 1}, 7: {W: 3}}
    ref = {0: {S: 1, E: 1}, 1: {S: 1, W: 1, E: 1}, 7: {W: 3}}
    s = _pos(cur, last="outmanoeuvre", ref=ref, courts=[{W: 1}])
    s.apply_action(OUT)
    assert F(1, E) in s.legal_actions()  # other completions remain
    s.apply_action(F(1, E))
    # The blocked sequence: pair {W,E} from Moray. Whatever the engine offers, it must never
    # let the full sequence be completed.
    t = _pos(cur, last="outmanoeuvre", ref=ref, courts=[{W: 1}])
    got = _explore(t, OUT, 3)
    assert (F(1, E), F(0, W), F(0, E)) not in got
    _check(_pos(cur, last="outmanoeuvre", ref=ref, courts=[{W: 1}]), OUT, _tb(ref))


def test_R216_example2_blocked_one_for_two_forces_one_for_one():
    """R-216 example 2 via the shipped scenario: Moray [W W], Strathclyde [S]; the only 1-for-2
    swap is blocked, so Outmanoeuvre is 1-for-1: PLAY(7) offers (Moray,W) only, then
    (Strathclyde,S) only, giving Moray [W S], Strathclyde [W]."""
    from kingisdead.scenario import load_scenario

    s = load_scenario(SCEN / "undo_block_outmanoeuvre.json")
    assert s.current_player() == 1
    s.apply_action(OUT)
    assert s.legal_actions() == [F(0, W)]
    s.apply_action(F(0, W))
    assert s.legal_actions() == [F(1, S)]
    s.apply_action(F(1, S))
    assert _counts(s)[0] == [1, 1, 0] and _counts(s)[1] == [0, 1, 0]


def test_R216_example2_via_real_play_from_pre_l_board():
    """R-216 example 2, end to end from the board before L: Moray [S], Strathclyde [W W], Devon
    [E]. Seat 0 plays Outmanoeuvre (Moray,S) for {W,W} and summons Devon's E; seat 1's only
    1-for-2 swap would reproduce B*, so Outmanoeuvre is 1-for-1: (Moray,W) then (Strathclyde,S)."""
    s = _pos({0: {S: 1}, 1: {W: 2}, 7: {E: 1}}, to_play=0)
    for a in (OUT, F(0, S), F(1, W), F(1, W), F(7, E)):
        s.apply_action(a)
    assert s.current_player() == 1
    assert _counts(s)[0] == [0, 2, 0] and _counts(s)[1] == [1, 0, 0]
    s.apply_action(OUT)
    assert s.legal_actions() == [F(0, W)]
    s.apply_action(F(0, W))
    assert s.legal_actions() == [F(1, S)]


def test_R216_example3_via_real_play_from_pre_l_board():
    """R-216 example 3, end to end: Moray [S E], Strathclyde [S W E], Devon [W W W W]. Seat 0
    plays Outmanoeuvre (Moray,S) for {S,W} from Strathclyde and summons a W from Devon. Seat 1
    picks (Strathclyde,E): the only Moray first pick is S (so the {W,E} pair that reproduces B*
    is not offered), then {S,W} or {S,E} complete the swap."""
    s = _pos({0: {S: 1, E: 1}, 1: {S: 1, W: 1, E: 1}, 7: {W: 4}}, to_play=0)
    for a in (OUT, F(0, S), F(1, S), F(1, W), F(7, W)):
        s.apply_action(a)
    assert s.current_player() == 1
    assert _counts(s)[0] == [1, 1, 1] and _counts(s)[1] == [1, 0, 1]
    s.apply_action(OUT)
    assert F(1, E) in s.legal_actions()
    s.apply_action(F(1, E))
    assert s.legal_actions() == [F(0, S)]
    s.apply_action(F(0, S))
    assert s.legal_actions() == [F(0, W), F(0, E)]


def test_R216_example2_blocked_form_is_absent_not_just_unpicked():
    """R-216 example 2: the blocked 1-for-2 sequence 7, (Strathclyde,S), (Moray,W), (Moray,W) is
    not a legal path, and the oracle comparison (mode 1-for-1) holds for the shipped scenario."""
    from kingisdead.scenario import load_scenario

    s = load_scenario(SCEN / "undo_block_outmanoeuvre.json")
    got = _explore(s, OUT, 2)
    assert set(got) == {(F(0, W), F(1, S))}
    ref = {0: {S: 1}, 1: {W: 2}}
    _check(load_scenario(SCEN / "undo_block_outmanoeuvre.json"), OUT, _tb(ref))


def test_R216_example4_void_reference_blocks_nothing():
    """R-216 example 4 / D22: B* void (L's summoned E came from Moray, which held no E before L):
    Moray [S S S], Essex [S E E E], every Manoeuvre swap is legal. A scenario with last_card
    manoeuvre and no reference_board behaves the same."""
    cur = {0: {S: 3}, 6: {S: 1, E: 3}}
    s = _pos(cur, last="manoeuvre", ref=None, courts=[{E: 1}])
    _check(s, MAN, None)
    s = _pos(cur, last="manoeuvre", ref=None, courts=[{E: 1}])
    s.apply_action(MAN)
    assert s.legal_actions() == [F(0, S)]
    s.apply_action(F(0, S))
    assert s.legal_actions() == [F(6, S), F(6, E)]


def test_R216_example4_void_through_real_play():
    """R-216 example 4, end to end (3 players): seat 0 swaps (Moray,S) with (Essex,E) and summons
    the E now in Moray. B* is void, so seat 1's Manoeuvre may pick (Moray,S) with (Essex,S) and
    the reverse-looking (Moray,S)/(Essex,E) etc.: the tree equals the unblocked oracle."""
    s = _pos({0: {S: 4}, 6: {E: 4}}, players=3, to_play=0)
    for a in (MAN, F(0, S), F(6, E), F(0, E)):
        s.apply_action(a)
    assert s.current_player() == 1
    assert _counts(s)[0] == [3, 0, 0] and _counts(s)[6] == [1, 0, 3]
    _check(s, MAN, None, players=3)


def _run_example(path):
    from kingisdead.scenario import load_scenario

    data = json.loads(path.read_text())
    ex = data["example"]
    s = load_scenario(path)
    legal_after = ex["expect"].get("legal_after", {})
    if "0" in legal_after:
        assert s.legal_actions() == legal_after["0"]
    for i, a in enumerate(ex["actions"], 1):
        assert a in s.legal_actions(), f"action {a} (step {i}) not legal: {s.legal_actions()}"
        s.apply_action(a)
        if str(i) in legal_after:
            assert s.legal_actions() == legal_after[str(i)], f"legal actions after {i} actions"
    counts = _counts(s)
    for name, cmap in ex["expect"]["regions"].items():
        r = REGIONS.index(name)
        assert counts[r] == [cmap.get(x, 0) for x in FN], name
    _conserved(s, data["players"])
    if ex["expect"].get("phase") == "SUMMON":
        assert s.legal_actions() == _present(counts)
    return s


def test_R216_shipped_example_undo_block_outmanoeuvre():
    """R-216 / SCENARIOS: undo_block_outmanoeuvre.json example block (actions 7,17,19) is legal
    step by step, the exact legal-action lists match and the board ends as documented."""
    _run_example(SCEN / "undo_block_outmanoeuvre.json")


def test_R216_shipped_example_undo_block_void():
    """R-216 (D22) / SCENARIOS: undo_block_void.json example block (7,16,21,21,18,7,18,19): the
    second player's 1-for-1 reproducing the pre-card board is NOT blocked (void B*)."""
    s = _run_example(SCEN / "undo_block_void.json")
    assert s.current_player() == 1


def test_R216_void_scenario_second_player_mode_is_one_for_one():
    """R-216 / R-215 with undo_block_void.json: after seat 0's play the position has no region
    with two followers, so seat 1's Outmanoeuvre is 1-for-1 and unblocked: the oracle with no
    B* matches the tree."""
    from kingisdead.scenario import load_scenario

    s = load_scenario(SCEN / "undo_block_void.json")
    for a in (7, 16, 21, 21, 18):
        s.apply_action(a)
    assert s.current_player() == 1
    depth, exp = _check(s, OUT, None)
    assert depth == 2
    assert (F(0, E), F(1, S)) in exp


def test_R216_summoned_follower_removed_from_reference():
    """R-216: B* is the pre-L board with L's summoned follower removed, so the post-summon board
    is one follower short of the pre-L board and a swap result can equal B*. Pre-L Moray [S],
    Strathclyde [W W]; L = 1-for-2 and summon of Moray's... here B* (with the summoned W gone from
    Strathclyde) is given directly: Moray [S], Strathclyde [W]; now Moray [W], Strathclyde [S]:
    the reverse 1-for-1 swap reproduces B* and is blocked, so Outmanoeuvre has no effect."""
    cur = {0: {W: 1}, 1: {S: 1}}
    ref = {0: {S: 1}, 1: {W: 1}}
    s = _pos(cur, last="outmanoeuvre", ref=ref, courts=[{W: 1}])
    s.apply_action(OUT)
    assert s.current_player() == 1
    assert s.legal_actions() == [F(0, W), F(1, S)]  # straight to SUMMON, no sub-steps
    assert _hand(s, 1).get(OUT, 0) == 0
    # Manoeuvre is a different type: not blocked.
    s = _pos(cur, last="outmanoeuvre", ref=ref, courts=[{W: 1}])
    s.apply_action(MAN)
    assert s.legal_actions() == [F(0, W)]
    # Same type L = manoeuvre: the Manoeuvre reverse is blocked; no effect.
    s = _pos(cur, last="manoeuvre", ref=ref, courts=[{W: 1}])
    s.apply_action(MAN)
    assert s.legal_actions() == [F(0, W), F(1, S)]
    # Outmanoeuvre after L = manoeuvre: not blocked.
    s = _pos(cur, last="manoeuvre", ref=ref, courts=[{W: 1}])
    s.apply_action(OUT)
    assert s.legal_actions() == [F(0, W)]


def test_R216_reference_compares_region_states():
    """R-216 / R-004: B* includes each region's state. Moray is now closed (Scottish), but open
    and empty in B*: a swap whose open-region contents equal B*'s is not blocked."""
    cur = {1: {W: 1}, 2: {E: 1}}
    ref = {1: {E: 1}, 2: {W: 1}}
    s = _pos(cur, closed={0: "S"}, last="manoeuvre", ref=ref, ref_closed={}, courts=[{S: 1}])
    s.apply_action(MAN)
    assert s.legal_actions() == [F(1, W)]
    s.apply_action(F(1, W))
    assert s.legal_actions() == [F(2, E)]
    # With the same closed state in B* the same swap is blocked (no effect: straight to SUMMON).
    s = _pos(cur, closed={0: "S"}, last="manoeuvre", ref=ref, courts=[{S: 1}])
    s.apply_action(MAN)
    assert s.legal_actions() == [F(1, W), F(2, E)]


def test_R216_noop_swap_blocked_when_reference_equals_board():
    """R-216 / PLAN D20: a same-faction no-op swap leaves B* equal to the current board, so every
    no-op swap is blocked. Moray [S S], Essex [S S], B* = same board: no Manoeuvre swap is legal
    at all (all are no-ops), so the card has no effect."""
    cur = {0: {S: 2}, 6: {S: 2}}
    s = _pos(cur, last="manoeuvre", ref=cur, courts=[{S: 1}])
    s.apply_action(MAN)
    assert s.legal_actions() == [F(0, S), F(6, S)]  # SUMMON immediately
    assert s.current_player() == 1


def test_R216_blocked_players_pick_in_other_order_also_blocked():
    """R-216: 'whichever region is picked first'. Manoeuvre's canonical order puts the lower
    region first, but Outmanoeuvre 1-for-2 can start from either side. Moray [S], Strathclyde
    [W W] reproduced by the swap from either side is blocked in both forms (ex. 2): with B* =
    Moray [W W], Strathclyde [S] the swap of (Moray,S)... see oracle."""
    cur = {0: {S: 1}, 1: {W: 2}}
    ref = {0: {W: 2}, 1: {S: 1}}
    s = _pos(cur, last="outmanoeuvre", ref=ref)
    depth, exp = _check(s, OUT, _tb(ref))
    assert depth == 2  # the only 1-for-2 swap reproduces B*; falls to 1-for-1
    assert (F(0, S), F(1, W)) in exp


# ================================================================ R-217 lifetime


def _a_board():
    """Board after seat 0's Manoeuvre of R-216 example 1 (3 players), B* attached by the
    scenario: pre-L Moray [S S S S], Essex [E E E E], Devon [W W W W]."""
    cur = {0: {S: 3, E: 1}, 6: {E: 3, S: 1}, 7: {W: 3}}
    ref = {0: {S: 4}, 6: {E: 4}, 7: {W: 3}}
    return cur, ref


def _man_from_a(**kw):
    cur, ref = _a_board()
    return _pos(cur, players=3, last="manoeuvre", ref=ref, courts=[{W: 1}], **kw), ref


def test_R217_block_applies_to_next_player_directly():
    """R-217 baseline: seat 1 immediately after L is blocked from the reverse swap."""
    s, ref = _man_from_a()
    _check(s, MAN, _tb(ref), players=3)
    s.apply_action(MAN)
    s.apply_action(F(0, E))
    assert F(6, S) not in s.legal_actions()


def test_R217_passes_do_not_clear_block():
    """R-217: a pass does not clear the record. Seat 0 played L, seat 1 passes, seat 2 plays
    Manoeuvre: the reverse swap is still blocked."""
    s, ref = _man_from_a()
    s.apply_action(0)  # PASS by seat 1
    assert s.current_player() == 2
    assert s.pass_count == 1
    _check(s, MAN, _tb(ref), players=3)
    s2, _ = _man_from_a()
    s2.apply_action(0)
    s2.apply_action(MAN)
    s2.apply_action(F(0, E))
    assert F(6, S) not in s2.legal_actions()
    assert F(6, E) in s2.legal_actions()


def test_R217_struggle_does_not_clear_but_nothing_can_match():
    """R-217 example: seat 0 Manoeuvres (L), 1, 2, 0 pass, a struggle resolves in Moray (slot 1,
    open in B*; Scottish 3 vs English 1: Scottish control) and seat 1 acts: Moray is now closed
    and empty, so no play can match B* and nothing is blocked."""
    s, ref = _man_from_a()
    for _ in range(3):
        s.apply_action(0)
    assert s.pass_count == 0
    assert s.current_player() == 1
    assert _counts(s)[0] == [0, 0, 0]
    _check(s, MAN, None, players=3)


def test_R217_other_card_play_clears_block():
    """R-217: any other card played replaces L and B*. Seat 1 plays Assemble with only one
    Scottish follower in the supply (placed on Strathclyde, then summoned back), restoring the
    board; seat 2's reverse swap would have matched the old B*, but is now legal."""
    cur, ref = _a_board()
    s = _pos(cur, players=3, last="manoeuvre", ref=ref, courts=[{W: 1}], supply={S: 1})
    for a in (4, region(1), F(1, S)):
        s.apply_action(a)
    assert s.current_player() == 2
    assert _tc(s) == _tb(cur)
    s.apply_action(MAN)
    s.apply_action(F(0, E))
    assert F(6, S) in s.legal_actions()
    s3 = _pos(cur, players=3, last="manoeuvre", ref=ref, courts=[{W: 1}], supply={S: 1})
    for a in (4, region(1), F(1, S)):
        s3.apply_action(a)
    _check(s3, MAN, None, players=3)


def test_R217_new_manoeuvre_replaces_reference():
    """R-217: a later Manoeuvre by seat 1 replaces L and B* with its own. Seat 1 swaps
    (Moray,S) with (Devon,W) and summons Essex's E; seat 2 is blocked against seat 1's B*
    (the board before seat 1's swap minus the E), not against seat 0's."""
    cur, ref = _a_board()
    s = _pos(cur, players=3, last="manoeuvre", ref=ref, courts=[{W: 1}])
    pre = _tc(s)
    for a in (MAN, F(0, S), F(7, W), F(6, E)):
        s.apply_action(a)
    assert s.current_player() == 2
    # B*' = pre-swap board with the summoned (Essex, E) removed (Essex held E before: not void).
    rows = [list(r) for r in pre]
    rows[6][E] -= 1
    bstar2 = tuple(tuple(r) for r in rows)
    _check(s, MAN, bstar2, players=3)
    # The reverse of seat 1's swap is blocked.
    u = s.clone()
    got = _explore(u, MAN, 2, players=3)
    assert (F(0, W), F(7, S)) not in got


def test_R217_no_swap_play_clears_block():
    """R-217 / R-216: L made no swap (no legal swap existed) so nothing is blocked. A position
    created with last_card manoeuvre and no reference board (the scenario form of 'no swap')
    blocks nothing, and a no-effect Manoeuvre by seat 1 on a one-region board followed by
    another seat's Manoeuvre blocks nothing. Note: a no-swap play followed by its summon leaves
    one follower fewer than the old B*, so the old B* can never match again; a mutant that keeps
    the old B* is therefore equivalent and this test cannot show the block being replaced."""
    s = _pos({3: {S: 3}}, players=3, last="manoeuvre", ref=None)
    s.apply_action(MAN)  # no effect
    assert s.legal_actions() == [F(3, S)]
    s.apply_action(F(3, S))
    assert s.current_player() == 2
    _check(s, MAN, None, players=3)


def test_R217_summon_is_part_of_l_not_new_card():
    """R-217: the summon completing L does not clear B*: after L (swap + summon) by seat 0 the
    next seat is blocked (end-to-end, 3 players, R-216 example 1)."""
    s = _pos({0: {S: 4}, 6: {E: 4}, 7: {W: 4}}, players=3, to_play=0)
    for a in (MAN, F(0, S), F(6, E), F(7, W)):
        s.apply_action(a)
    bstar = _tb({0: {S: 4}, 6: {E: 4}, 7: {W: 3}})
    _check(s, MAN, bstar, players=3)
