"""Acceptance tests for the power struggle: R-300..R-304 (Phase 2 unit 8), with the trigger R-105,
the turn order R-100 after a struggle and conservation R-015.

Assumed identifiers (same style as test_setup.py / test_assemble_negotiate.py):
  s.region_counts[r][f], s.courts[p][f], s.supply[f], s.hands[p], s.pass_count,
  s.struggles_resolved, s.slot_regions[i] (region on the card in slot i+1),
  s.region_states[r] (``kingisdead.constants.REGION_OPEN / REGION_CONTROLLED / REGION_UNSTABLE``),
  s.region_control[r] (faction index of the controlling faction for a controlled region; for an
    open or unstable region ``None`` or -1 - the tests accept either),
  s.recent_win[f] (struggle number of the faction's latest win, -1 if none; R-303),
  s.negotiation_discs[p]; ``kingisdead.scenario.load_scenario(dict)``;
  PASS = 0, PLAY(c) = c, REGION(r) = 8 + r, FOLLOWER(r, f) = 16 + 3r + f.
The struggle is automatic: it runs inside the PASS that makes the pass count reach n.
Positions are scenarios (SCENARIOS.md): the first ``len(closed)`` slots are face down (V4), the
rest of ``slots`` follows ``order`` (or ascending region index). By default the pass count is
n - 1, so the next PASS triggers the struggle; seat ``to_play`` makes that last pass.
Expected results are computed by the small oracle ``_expect`` from R-300..R-303, not hard-coded,
where a whole game is walked. Final returns/scoring are R-400..R-405 (unit 9) and not tested here.
"""

import copy

import pytest

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
FN = ["S", "W", "E"]
POOL = {2: 16, 3: 18}
PASS = 0
S, W, E = 0, 1, 2
CLOSE = {"S": S, "W": W, "E": E}


def _c():
    from kingisdead import constants

    return constants


# ---------------------------------------------------------------- state building


def _pos(
    *,
    players=2,
    board=None,
    closed=None,
    order=None,
    supply=None,
    courts=None,
    to_play=0,
    pass_count=None,
    extra=None,
):
    """State from a scenario. ``board``: {region: {faction: n}} on open regions; ``closed``:
    ordered {region: 'S'|'W'|'E'|'unstable'} occupying slots 1..k; ``order``: the open regions in
    slot order after the closed ones (default ascending); ``supply``: {faction: n} (default 0);
    ``courts``: list of {faction: n} for the first seats, the remainder of each pool goes to
    the last seat's court; ``extra``: dict merged into the scenario."""
    from kingisdead.scenario import load_scenario

    board = board or {}
    closed = closed or {}
    supply = {0: 0, 1: 0, 2: 0, **(supply or {})}
    courts = [dict(c) for c in (courts or [])]
    courts += [{} for _ in range(players - len(courts))]
    for f in range(3):
        used = (
            sum(c.get(f, 0) for c in board.values()) + sum(c.get(f, 0) for c in courts) + supply[f]
        )
        rest = POOL[players] - used
        assert rest >= 0
        courts[-1][f] = courts[-1].get(f, 0) + rest
    rest_regions = [r for r in range(8) if r not in closed]
    open_order = list(order) if order is not None else rest_regions
    assert sorted(open_order) == rest_regions
    slots = list(closed) + open_order

    def cm(c):
        return {FN[f]: n for f, n in c.items() if n}

    data = {
        "format": 1,
        "kind": "state",
        "players": players,
        "slots": [REGIONS[r] for r in slots],
        "regions": {REGIONS[r]: cm(c) for r, c in board.items() if cm(c)},
        "courts": [cm(c) for c in courts],
        "to_play": to_play,
        "pass_count": players - 1 if pass_count is None else pass_count,
        "struggles": len(closed),
        "region_state": {REGIONS[r]: v for r, v in closed.items()},
    }
    data.update(extra or {})
    return load_scenario(copy.deepcopy(data))


def _counts(s):
    return [list(map(int, row)) for row in s.region_counts]


def _supply(s):
    return list(map(int, s.supply))


def _courts(s, players):
    return [list(map(int, s.courts[p])) for p in range(players)]


def _conserved(s, players):
    c = _counts(s)
    for f in range(3):
        total = (
            sum(row[f] for row in c)
            + sum(int(s.courts[p][f]) for p in range(players))
            + int(s.supply[f])
        )
        assert total == POOL[players], f"faction {f}: {total}"


def _controller(s, r):
    v = s.region_control[r]
    return None if v is None or v == -1 else int(v)


def _unstable(s):
    c = _c()
    return sum(1 for st in s.region_states if st == c.REGION_UNSTABLE)


def _wins(s):
    return list(map(int, s.recent_win))


def _expect(s):
    """R-300..R-303 oracle on the state before the triggering pass: (region, winner|None)."""
    r = s.slot_regions[s.struggles_resolved]
    row = _counts(s)[r]
    top = max(row)
    if top > 0 and sum(1 for x in row if x == top) == 1:
        return r, row.index(top)
    return r, None


def _check_struggle(s, players):
    """Apply the triggering PASS to ``s`` (pass count n-1) and check R-300..R-304 against the
    oracle. Returns the state after (the same object)."""
    c = _c()
    r, winner = _expect(s)
    k = s.struggles_resolved
    before_counts = _counts(s)
    before_supply = _supply(s)
    before_courts = _courts(s, players)
    before_wins = _wins(s)
    before_unstable = _unstable(s)
    slots = list(s.slot_regions)
    mover = s.current_player()
    s.apply_action(PASS)
    assert s.struggles_resolved == k + 1
    assert s.pass_count == 0
    assert list(s.slot_regions) == slots
    assert _counts(s)[r] == [0, 0, 0]
    for x in range(8):
        if x != r:
            assert _counts(s)[x] == before_counts[x]
    exp_supply = [before_supply[f] + before_counts[r][f] for f in range(3)]
    assert _supply(s) == exp_supply
    assert _courts(s, players) == before_courts
    if winner is None:
        assert s.region_states[r] == c.REGION_UNSTABLE
        assert _unstable(s) == before_unstable + 1
        assert _wins(s) == before_wins
    else:
        assert s.region_states[r] == c.REGION_CONTROLLED
        assert _controller(s, r) == winner
        exp_wins = list(before_wins)
        exp_wins[winner] = k + 1
        assert _wins(s) == exp_wins
    _conserved(s, players)
    ended = _unstable(s) == 3 or k + 1 == 8
    assert s.is_terminal() == ended
    if not ended:
        assert s.current_player() == (mover + 1) % players
    return s


def _closed_seven(states):
    """Seven closed regions 0..6 with the given states; Devon (7) stays open in slot 8."""
    return {r: st for r, st in enumerate(states)}


# ================================================================ R-300 contested region


@pytest.mark.parametrize(
    "order",
    [
        [2, 0, 1, 3, 4, 5, 6, 7],
        [7, 0, 1, 2, 3, 4, 5, 6],
        [6, 7, 5, 4, 3, 2, 1, 0],
        [3, 5, 7, 0, 1, 2, 4, 6],
    ],
)
def test_R300_lowest_slot_region_is_contested(order):
    """R-300: with every card face up the region in slot 1 is contested, whatever its index. Every
    open region holds followers; only the slot-1 region is closed and emptied."""
    c = _c()
    board = {r: {S: 1, W: 1} for r in range(8)}
    s = _pos(board=board, order=order)
    s.apply_action(PASS)
    first = order[0]
    assert s.region_states[first] != c.REGION_OPEN
    assert _counts(s)[first] == [0, 0, 0]
    for r in range(8):
        if r != first:
            assert s.region_states[r] == c.REGION_OPEN
            assert _counts(s)[r] == [1, 1, 0]


def test_R300_example_next_face_up_slot_after_face_down_ones():
    """R-300: face-down cards are skipped: slots 1, 2 face down (struggles = 2), so slot 3's region
    (Northumbria here, with the remaining order Northumbria, Moray, ...) is contested."""
    c = _c()
    board = {r: {W: 2, E: 1} for r in (0, 1, 3, 4, 6, 7)}
    board[3] = {S: 3}
    s = _pos(board=board, closed={5: "S", 2: "unstable"}, order=[3, 0, 1, 4, 6, 7])
    assert s.struggles_resolved == 2
    s.apply_action(PASS)
    assert s.struggles_resolved == 3
    assert s.region_states[3] == c.REGION_CONTROLLED
    assert _controller(s, 3) == S
    assert _counts(s)[3] == [0, 0, 0]
    # The later slots are untouched.
    assert _counts(s)[0] == [0, 2, 1] and s.region_states[0] == c.REGION_OPEN


def test_R300_successive_struggles_follow_slot_order():
    """R-300 / R-303: two consecutive struggles contest slot 1 then slot 2 (struggle number k is
    in slot k). Slots Warwick, Moray, then the rest."""
    c = _c()
    board = {5: {E: 2}, 0: {S: 2}, 1: {W: 1}}
    s = _pos(board=board, order=[5, 0, 1, 2, 3, 4, 6, 7])
    s.apply_action(PASS)
    assert s.region_states[5] != c.REGION_OPEN and s.region_states[0] == c.REGION_OPEN
    assert s.struggles_resolved == 1
    s.apply_action(PASS)  # pass count 1 (of 2): no struggle yet
    assert s.struggles_resolved == 1
    s.apply_action(PASS)  # 2nd consecutive pass: second struggle, in Moray
    assert s.struggles_resolved == 2
    assert s.region_states[0] != c.REGION_OPEN
    assert s.region_states[1] == c.REGION_OPEN and _counts(s)[1] == [0, 1, 0]


def test_R300_negotiated_order_changes_contested_region():
    """R-300 / R-213: Negotiate swapping the cards of Moray (slot 1) and Devon (slot 8) puts Devon
    in slot 1; after the play both players pass and the struggle is in Devon, not Moray."""
    c = _c()
    board = {0: {S: 4}, 7: {W: 3}, 3: {E: 2}}
    s = _pos(board=board, pass_count=0, to_play=0)
    for a in (5, 8 + 0, 8 + 7, 8 + 7):  # PLAY(Negotiate), REGION(0), REGION(7), disc on Devon
        assert a in s.legal_actions()
        s.apply_action(a)
    assert list(s.slot_regions)[0] == 7 and list(s.slot_regions)[7] == 0
    if s.current_player() == 0:  # summon (any follower, if the board still has one)
        s.apply_action(s.legal_actions()[0])
    assert s.current_player() == 1
    r, winner = _expect(s)
    assert r == 7
    s.apply_action(PASS)
    s.apply_action(PASS)
    assert s.struggles_resolved == 1
    assert s.region_states[7] != c.REGION_OPEN
    assert s.region_states[0] == c.REGION_OPEN


def test_R300_region_card_with_negotiation_disc_is_still_contested():
    """R-300 (boundary): a card carrying a negotiation disc is still a face-up card; the disc does
    not stop it from being the contested region, and it stays on the (now face-down) card."""
    c = _c()
    hand = ["scottish_support", "welsh_support", "english_support", "assemble", "assemble"]
    full = [*hand, "manoeuvre", "outmanoeuvre"]
    extra = {
        "negotiation": ["Lancaster", None],
        "hands": [full, list(full + ["negotiate"])],
        "last_play": [1, None],
        "last_card": {"type": "negotiate"},
    }
    s = _pos(board={2: {S: 2}, 3: {W: 1}}, order=[2, 3, 0, 1, 4, 5, 6, 7], extra=extra)
    s.apply_action(PASS)
    assert s.region_states[2] == c.REGION_CONTROLLED
    assert s.negotiation_discs[0] == 2
    assert s.struggles_resolved == 1


# ================================================================ R-301 winner


CASES = [
    # (followers in the contested region, winner or None)
    ({S: 2, W: 1, E: 1}, S),  # R-301 example [S S W E]
    ({S: 2, W: 2}, None),  # [S S W W]
    ({}, None),  # []
    ({S: 1, W: 1, E: 1}, None),  # [S W E]
    ({E: 1}, E),  # a single follower is strictly more than each other (0) and at least 1
    ({W: 1}, W),
    ({S: 5, W: 4, E: 4}, S),
    ({S: 3, W: 3, E: 3}, None),
    ({W: 3, E: 3, S: 1}, None),  # two-way tie at the top, third faction below
    ({E: 4, W: 2, S: 2}, E),  # a tie below the top does not matter
    ({S: 2, E: 1, W: 0}, S),
    ({W: 6}, W),
    ({S: 2, W: 2, E: 2}, None),
]


@pytest.mark.parametrize("players", [2, 3])
@pytest.mark.parametrize("counts,winner", CASES)
def test_R301_winner_is_strict_maximum(counts, winner, players):
    """R-301: the faction with strictly more followers than each other faction (and at least 1)
    controls the region (control disc, region_control); any tie for most, including an empty
    region, makes it unstable (instability disc from France)."""
    c = _c()
    s = _pos(players=players, board={2: counts, 5: {S: 1}}, order=[2, 5, 0, 1, 3, 4, 6, 7])
    s.apply_action(PASS if players == 2 else PASS)
    # the pass count is players - 1 so this pass is the triggering one
    assert s.struggles_resolved == 1
    if winner is None:
        assert s.region_states[2] == c.REGION_UNSTABLE
        assert _controller(s, 2) is None
        assert _unstable(s) == 1
    else:
        assert s.region_states[2] == c.REGION_CONTROLLED
        assert _controller(s, 2) == winner
        assert _unstable(s) == 0


def test_R301_courts_and_supply_do_not_count():
    """R-301 (negative): only followers in the contested region are counted: a Scottish follower
    in the region wins although the courts and the supply hold many English and Welsh."""
    c = _c()
    s = _pos(
        board={2: {S: 1}},
        courts=[{E: 7, W: 6}, {E: 6, W: 5}],
        supply={E: 3, W: 5},
        order=[2, 0, 1, 3, 4, 5, 6, 7],
    )
    s.apply_action(PASS)
    assert s.region_states[2] == c.REGION_CONTROLLED
    assert _controller(s, 2) == S


def test_R301_home_region_can_be_won_by_another_faction():
    """R-301: nothing ties control to a faction's home: English win Moray (the Scottish home), and
    an Essex (English home) with 1 English vs 2 Welsh goes to the Welsh."""
    c = _c()
    s = _pos(board={0: {E: 2, S: 1}, 6: {E: 1, W: 2}}, order=[0, 6, 1, 2, 3, 4, 5, 7])
    s.apply_action(PASS)
    assert _controller(s, 0) == E and s.region_states[0] == c.REGION_CONTROLLED
    s.apply_action(PASS)
    s.apply_action(PASS)
    assert _controller(s, 6) == W and s.region_states[6] == c.REGION_CONTROLLED


def test_R301_only_the_contested_region_is_evaluated():
    """R-301 (negative): other regions that would be won or tied stay open with their followers."""
    c = _c()
    s = _pos(board={2: {S: 2}, 3: {W: 3}, 4: {}, 5: {E: 1, S: 1}}, order=[2, 3, 4, 5, 0, 1, 6, 7])
    s.apply_action(PASS)
    for r in (3, 5):
        assert s.region_states[r] == c.REGION_OPEN
        assert _controller(s, r) is None
    assert _counts(s)[3] == [0, 3, 0] and _counts(s)[5] == [1, 0, 1]
    assert _unstable(s) == 0


# ================================================================ R-302 followers leave


def test_R302_example_followers_return_to_supply():
    """R-302 example: a region [S S W E] controlled by the Scots: the supply gains 2 Scottish,
    1 Welsh, 1 English and the region is empty; the winner's followers do not stay."""
    s = _pos(
        board={2: {S: 2, W: 1, E: 1}},
        supply={S: 3, W: 2, E: 1},
        order=[2, 0, 1, 3, 4, 5, 6, 7],
    )
    assert _supply(s) == [3, 2, 1]
    s.apply_action(PASS)
    assert _counts(s)[2] == [0, 0, 0]
    assert _supply(s) == [5, 3, 2]
    _conserved(s, 2)


def test_R302_unstable_region_also_empties_to_supply():
    """R-302: followers of an unstable result go to the supply too, not to a court or an off-board
    area; the courts are unchanged."""
    s = _pos(
        players=3,
        board={2: {S: 2, W: 2, E: 1}},
        courts=[{S: 1, W: 2}, {E: 3}],
        supply={S: 1},
        order=[2, 0, 1, 3, 4, 5, 6, 7],
    )
    courts_before = _courts(s, 3)
    sup = _supply(s)
    s.apply_action(PASS)
    assert _counts(s)[2] == [0, 0, 0]
    assert _supply(s) == [sup[0] + 2, sup[1] + 2, sup[2] + 1]
    assert _courts(s, 3) == courts_before
    _conserved(s, 3)


def test_R302_other_regions_keep_their_followers():
    """R-302 (negative): only the contested region is cleared."""
    board = {2: {S: 3}, 0: {S: 2, W: 2}, 7: {E: 4}}
    s = _pos(board=board, order=[2, 0, 7, 1, 3, 4, 5, 6])
    s.apply_action(PASS)
    assert _counts(s)[0] == [2, 2, 0]
    assert _counts(s)[7] == [0, 0, 4]
    assert _supply(s) == [3, 0, 0]


def test_R302_empty_region_changes_nothing_in_the_supply():
    """R-302 boundary: an empty contested region is unstable and the supply is unchanged."""
    s = _pos(board={3: {W: 1}}, supply={S: 2, E: 1}, order=[2, 3, 0, 1, 4, 5, 6, 7])
    before = _supply(s)
    s.apply_action(PASS)
    assert _supply(s) == before


def test_R302_closed_regions_hold_no_followers_after_every_struggle():
    """R-302 / R-015: after each struggle of a pass-only game every closed region is empty."""
    c = _c()
    board = {r: {S: 1 + r % 2, W: 1, E: r % 3} for r in range(8)}
    s = _pos(board=board)
    while not s.is_terminal():
        for _ in range(2):
            if s.is_terminal():
                break
            s.apply_action(PASS)
        for r in range(8):
            if s.region_states[r] != c.REGION_OPEN:
                assert _counts(s)[r] == [0, 0, 0]
    _conserved(s, 2)


# ================================================================ R-303 flip and record


def test_R303_card_stays_in_slot_and_region_closes():
    """R-303: the contested card is turned face down but stays in its slot; the closed region
    cannot be contested again: the next struggle is in slot 2."""
    c = _c()
    order = [4, 6, 1, 0, 2, 3, 5, 7]
    s = _pos(board={4: {W: 2}, 6: {E: 1}, 1: {S: 1}}, order=order)
    s.apply_action(PASS)
    assert list(s.slot_regions) == order
    assert s.region_states[4] == c.REGION_CONTROLLED
    s.apply_action(PASS)
    s.apply_action(PASS)
    assert list(s.slot_regions) == order
    assert s.region_states[6] == c.REGION_CONTROLLED
    assert _controller(s, 6) == E
    assert _controller(s, 4) == W  # an earlier result never changes


def test_R303_struggle_counter_and_first_struggle_is_number_one():
    """R-303: the struggle count starts at 0 and the first struggle is number 1: a win in the
    first struggle sets that faction's recent-win to 1 (all others -1)."""
    s = _pos(board={0: {S: 2, W: 1}}, order=[0, 1, 2, 3, 4, 5, 6, 7])
    assert s.struggles_resolved == 0
    assert _wins(s) == [-1, -1, -1]
    s.apply_action(PASS)
    assert s.struggles_resolved == 1
    assert _wins(s) == [1, -1, -1]


def test_R303_example_third_struggle_welsh_recent_win_three():
    """R-303 example: the third struggle gives the Welsh control: Welsh recent-win = 3, while the
    Scottish win of struggle 1 (derived from the scenario) stays 1 and an unstable struggle 2
    records nothing."""
    s = _pos(
        board={3: {W: 3, S: 1}},
        closed={0: "S", 1: "unstable"},
        order=[3, 2, 4, 5, 6, 7],
    )
    assert _wins(s) == [1, -1, -1]
    s.apply_action(PASS)
    assert s.struggles_resolved == 3
    assert _wins(s) == [1, 3, -1]


def test_R303_later_win_replaces_earlier_for_same_faction():
    """R-303: 'most recent' - a second Welsh win overwrites the first."""
    s = _pos(board={5: {W: 2}}, closed={4: "W"}, order=[5, 0, 1, 2, 3, 6, 7])
    assert _wins(s) == [-1, 1, -1]
    s.apply_action(PASS)
    assert _wins(s) == [-1, 2, -1]


def test_R303_unstable_result_records_nothing():
    """R-303: an unstable result changes no recent-win value, but still counts as a struggle and
    places an instability disc."""
    c = _c()
    s = _pos(board={2: {S: 1, W: 1}}, closed={0: "E"}, order=[2, 1, 3, 4, 5, 6, 7])
    before = _wins(s)
    assert before == [-1, -1, 1]
    s.apply_action(PASS)
    assert s.struggles_resolved == 2
    assert s.region_states[2] == c.REGION_UNSTABLE
    assert _wins(s) == before
    assert _unstable(s) == 1


def test_R303_controlled_region_records_controller_faction():
    """R-303 / R-004: the control disc is of the winning faction and the region becomes controlled
    (not unstable); all three factions are testable in turn."""
    c = _c()
    for winner in (S, W, E):
        s = _pos(board={7: {winner: 2}}, order=[7, 0, 1, 2, 3, 4, 5, 6])
        s.apply_action(PASS)
        assert s.region_states[7] == c.REGION_CONTROLLED
        assert _controller(s, 7) == winner
        assert _wins(s)[winner] == 1


def test_R303_hands_and_negotiation_discs_unchanged():
    """R-303 / R-105 (negative): a struggle changes no hand and no negotiation disc."""
    s = _pos(board={0: {S: 1}})
    hands = [dict(s.hands[p]) for p in range(2)]
    s.apply_action(PASS)
    assert [dict(s.hands[p]) for p in range(2)] == hands
    assert [s.negotiation_discs[p] for p in range(2)] == [None, None]


# ================================================================ R-304 after a struggle


@pytest.mark.parametrize("players", [2, 3])
def test_R304_play_continues_after_a_non_final_struggle(players):
    """R-304 / R-105: after the first struggle the pass count is 0 and the game is not over:
    the next player may pass or play any card in hand."""
    s = _pos(players=players, board={0: {S: 1}, 1: {W: 1}})
    for _ in range(1):
        s.apply_action(PASS)
    assert s.pass_count == 0
    assert not s.is_terminal()
    legal = s.legal_actions()
    assert PASS in legal and set(range(1, 8)) <= set(legal)


@pytest.mark.parametrize("players,last", [(2, 0), (2, 1), (3, 0), (3, 1), (3, 2)])
def test_R304_next_player_is_after_the_last_passer(players, last):
    """R-304 / R-100 / R-105: whoever makes the last pass, the next player to act is the seat after
    them (wrapping)."""
    s = _pos(players=players, board={0: {S: 1}}, to_play=last)
    s.apply_action(PASS)
    assert s.current_player() == (last + 1) % players


def test_R304_two_players_card_then_two_passes_gives_struggle():
    """R-105 / R-104: 2 players: seat 0 plays Manoeuvre (no swap: all in one region), summons;
    seat 1 passes (count 1), seat 0 passes (count 2) -> struggle and seat 1 acts."""
    s = _pos(board={3: {S: 2, E: 2}}, pass_count=0, to_play=0)
    s.apply_action(6)
    while s.current_player() == 0 and not s.is_terminal():
        s.apply_action(s.legal_actions()[0])
    assert s.current_player() == 1
    assert s.pass_count == 0
    s.apply_action(PASS)
    assert s.pass_count == 1 and s.struggles_resolved == 0
    s.apply_action(PASS)
    assert s.struggles_resolved == 1
    assert s.pass_count == 0
    assert s.current_player() == 1


def test_R304_card_play_resets_count_so_no_struggle_on_one_more_pass():
    """R-104 / R-105 (negative): with count n - 1, a card play (not a pass) resets the count and
    triggers no struggle; the next pass only makes the count 1."""
    s = _pos(players=3, board={3: {S: 2, E: 2}}, to_play=1)  # count 2
    s.apply_action(6)
    while s.current_player() == 1:
        s.apply_action(s.legal_actions()[0])
    assert s.struggles_resolved == 0
    assert s.pass_count == 0
    s.apply_action(PASS)
    assert s.pass_count == 1 and s.struggles_resolved == 0


def test_R304_eighth_struggle_ends_the_game_coronation():
    """R-304: with two unstable regions, the eighth struggle (controlled) ends the game; there are
    no legal actions and no ninth struggle can happen."""
    states = ["S", "unstable", "W", "E", "unstable", "S", "W"]
    s = _pos(board={7: {E: 3, S: 1}}, closed=_closed_seven(states), to_play=0)
    assert s.struggles_resolved == 7
    assert not s.is_terminal()
    s.apply_action(PASS)
    assert s.struggles_resolved == 8
    assert s.is_terminal()
    assert s.legal_actions() == []
    assert _unstable(s) == 2


def test_R304_eighth_struggle_unstable_with_one_earlier_still_coronation_ends_game():
    """R-304: the eighth struggle ends the game even when it adds a (second) instability disc."""
    states = ["S", "W", "E", "S", "W", "E", "unstable"]
    s = _pos(board={7: {E: 2, S: 2}}, closed=_closed_seven(states))
    s.apply_action(PASS)
    assert s.struggles_resolved == 8 and s.is_terminal()
    assert _unstable(s) == 2


def test_R304_third_instability_disc_ends_game_early_invasion():
    """R-304 / R-400: the struggle that places the third instability disc ends the game at once,
    although only the third struggle has been resolved; no more struggle happens."""
    s = _pos(board={5: {S: 1, W: 1}, 6: {E: 2}}, closed={0: "unstable", 1: "unstable"})
    assert s.struggles_resolved == 2 and not s.is_terminal()
    s.apply_action(PASS)
    assert s.struggles_resolved == 3
    assert _unstable(s) == 3
    assert s.is_terminal()
    assert s.legal_actions() == []


def test_R304_third_disc_at_the_eighth_struggle_is_still_terminal():
    """R-304: if the eighth struggle makes the third instability disc the game is an invasion; the
    terminal flag and struggle count are the same either way (scoring: unit 9)."""
    states = ["unstable", "S", "unstable", "W", "E", "S", "W"]
    s = _pos(board={7: {S: 1, W: 1}}, closed=_closed_seven(states))
    s.apply_action(PASS)
    assert s.struggles_resolved == 8
    assert _unstable(s) == 3
    assert s.is_terminal()


def test_R304_two_unstable_and_a_controlled_third_struggle_does_not_end_game():
    """R-304 (negative): two instability discs and a controlled third struggle: neither invasion
    nor coronation applies, play continues and the pass count is 0."""
    s = _pos(board={2: {S: 2}, 6: {E: 1}}, closed={0: "unstable", 1: "unstable"})
    s.apply_action(PASS)
    assert s.struggles_resolved == 3
    assert _unstable(s) == 2
    assert not s.is_terminal()
    assert s.pass_count == 0
    assert PASS in s.legal_actions()


def test_R304_seventh_struggle_does_not_end_game():
    """R-304 (negative): the seventh struggle with at most two unstable regions leaves the game
    running with exactly one face-up card."""
    states = ["S", "W", "E", "S", "W", "E"]
    s = _pos(board={6: {S: 1}, 7: {W: 2}}, closed=_closed_seven(states[:6]), order=[6, 7])
    assert s.struggles_resolved == 6
    s.apply_action(PASS)
    assert s.struggles_resolved == 7
    assert not s.is_terminal()
    assert _counts(s)[7] == [0, 2, 0]


@pytest.mark.parametrize("players", [2, 3])
def test_R304_empty_board_three_instabilities_end_game_after_three_struggles(players):
    """R-304 / R-106: with no followers on the board every struggle is unstable, so n passes x 3
    end the game by invasion after the third struggle."""
    s = _pos(players=players, pass_count=0)
    passes = 0
    while not s.is_terminal():
        s.apply_action(PASS)
        passes += 1
        assert passes <= 3 * players
    assert passes == 3 * players
    assert s.struggles_resolved == 3
    assert _unstable(s) == 3


# ================================================================ R-105 trigger / R-100 order


@pytest.mark.parametrize("players", [2, 3])
def test_R105_struggle_only_on_the_nth_consecutive_pass(players):
    """R-105: from count 0 the first n - 1 passes only count; the nth makes a struggle and the
    count returns to 0 (next player the one after the nth passer, here seat 0)."""
    s = _pos(players=players, board={0: {S: 1}}, pass_count=0)
    for i in range(players - 1):
        s.apply_action(PASS)
        assert s.pass_count == i + 1 and s.struggles_resolved == 0
    s.apply_action(PASS)
    assert s.struggles_resolved == 1 and s.pass_count == 0
    assert s.current_player() == 0


def test_R105_example_three_players_player_two_acts_next():
    """R-105 example: 3 players: seat 1 plays a card (sub-steps and summon completed), then seats
    2, 0, 1 pass -> struggle and seat 2 acts next."""
    s = _pos(players=3, board={3: {S: 2, E: 2}}, pass_count=0, to_play=1)
    s.apply_action(6)
    while s.current_player() == 1:
        s.apply_action(s.legal_actions()[0])
    assert s.current_player() == 2
    for expected_mover in (2, 0, 1):
        assert s.current_player() == expected_mover
        s.apply_action(PASS)
    assert s.struggles_resolved == 1
    assert s.pass_count == 0
    assert s.current_player() == 2


def test_R105_struggles_happen_again_after_n_more_passes():
    """R-105: the count restarts at 0 after a struggle, so n further consecutive passes are needed
    for the next one (3 players: 2 passes do nothing, the 3rd resolves struggle 2)."""
    s = _pos(players=3, board={0: {S: 1}, 1: {W: 1}}, pass_count=2, to_play=2)
    s.apply_action(PASS)
    assert s.struggles_resolved == 1 and s.current_player() == 0
    s.apply_action(PASS)
    s.apply_action(PASS)
    assert s.struggles_resolved == 1 and s.pass_count == 2
    s.apply_action(PASS)
    assert s.struggles_resolved == 2


# ================================================================ R-015 whole pass-only game


BOARDS = {
    "mixed": {r: {S: 1 + r % 3, W: (r * 2) % 3, E: (r + 1) % 2} for r in range(8)},
    "winners": {0: {S: 3}, 1: {W: 2, S: 1}, 2: {E: 2}, 3: {S: 1, W: 1}, 4: {W: 4}, 5: {E: 1}},
    "ties": {r: {S: 1, W: 1} for r in range(8)},
}


@pytest.mark.parametrize("players", [2, 3])
@pytest.mark.parametrize("name", sorted(BOARDS))
def test_R015_conservation_and_oracle_over_whole_pass_only_game(name, players):
    """R-015 / R-300..R-304: starting from a full table of unresolved regions, the engine and the
    independent oracle agree on every struggle until the game ends (3 unstable or the 8th
    struggle), followers are conserved after each, and the game cannot outlast 8 struggles."""
    board = BOARDS[name]
    s = _pos(players=players, board=board, pass_count=0)
    struggles = 0
    for _ in range(8 * players):
        if s.is_terminal():
            break
        for i in range(players):
            if i == players - 1:
                _check_struggle(s, players)
            else:
                s.apply_action(PASS)
                _conserved(s, players)
        struggles += 1
    assert s.is_terminal()
    assert s.struggles_resolved == struggles <= 8
    assert _unstable(s) == 3 or s.struggles_resolved == 8
    for r in range(8):
        assert _counts(s)[r] == [0, 0, 0] or s.region_states[r] == _c().REGION_OPEN


def test_R015_conservation_after_struggle_with_court_followers():
    """R-015: followers in courts and supply are conserved around a struggle, and a closed region
    holds zero."""
    s = _pos(
        players=3,
        board={2: {S: 2, E: 2}, 3: {W: 1}},
        courts=[{S: 4, W: 3}, {E: 5, W: 2}],
        supply={S: 2, W: 1, E: 1},
        order=[2, 3, 0, 1, 4, 5, 6, 7],
    )
    _conserved(s, 3)
    _check_struggle(s, 3)
    _conserved(s, 3)
