"""Acceptance tests for Support cards, placement and summon: R-200, R-201, R-202, R-210, R-211
(Phase 2 unit 5).

Assumed identifiers (as in test_setup.py / test_turn_start.py):
  s.region_counts[r][f], s.courts[p][f], s.supply[f], s.hands[p] (card id -> copies),
  s.pass_count, s.plays_total, s.struggles_resolved; public API legal_actions(), current_player(),
  apply_action(), clone(); ``kingisdead.scenario.load_scenario(dict_or_path)`` returns a state.
The current phase is NOT read from the state: it is inferred from legal_actions()
(ids 8..15 = a REGION target step, ids >= 16 = SUMMON, ids 0..7 = TURN_START).
Action ids per docs/ACTIONS.md section 2: PLAY(c) = c (Support: 1 Scottish, 2 Welsh, 3 English),
REGION(r) = 8 + r, FOLLOWER(r, f) = 16 + 3r + f.
Positions are built from "state" scenarios (docs/SCENARIOS.md) by ``_pos``; the expected sets
of eligible regions are computed here independently from R-002/R-003/R-210.
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
HOME = {0: 0, 1: 4, 2: 6}
FN = ["S", "W", "E"]
POOL = 16  # 2-player game
START_HAND = {1: 1, 2: 1, 3: 1, 4: 2, 5: 1, 6: 1, 7: 1}

PASS = 0


def region(r):
    return 8 + r


def follower(r, f):
    return 16 + 3 * r + f


def _pos(regions=None, closed=None, supply=None, pass_count=0):
    """Build a 2-player state. ``regions``: {region index: {faction index: n}} (default: one
    follower of each faction on every open region); ``closed``: ordered {region index: 'S'|'W'|
    'E'|'unstable'} (these take slots 1..k, V4); ``supply``: {faction index: n} (default 3 each,
    the remainder of the pool sits in seat 1's court)."""
    from kingisdead.scenario import load_scenario

    closed = closed or {}
    if regions is None:
        regions = {r: {0: 1, 1: 1, 2: 1} for r in range(8) if r not in closed}
    supply = {0: 3, 1: 3, 2: 3, **(supply or {})}
    slots = list(closed) + [r for r in range(8) if r not in closed]
    court1 = {}
    for f in range(3):
        used = sum(c.get(f, 0) for c in regions.values())
        rest = POOL - used - supply[f]
        assert rest >= 0
        if rest:
            court1[FN[f]] = rest
    data = {
        "format": 1,
        "kind": "state",
        "players": 2,
        "slots": [REGIONS[r] for r in slots],
        "regions": {REGIONS[r]: {FN[f]: n for f, n in c.items() if n} for r, c in regions.items()},
        "courts": [{}, court1],
        "to_play": 0,
        "struggles": len(closed),
        "region_state": {REGIONS[r]: v for r, v in closed.items()},
        "pass_count": pass_count,
    }
    return load_scenario(copy.deepcopy(data))


def _eligible(faction, closed):
    """R-210 reference: set of eligible region indices."""
    home = HOME[faction]
    out = set()
    for r in range(8):
        if r in closed:
            continue
        via_a = any(closed.get(n) == FN[faction] for n in ADJ[r])
        via_b = home not in closed and r in ADJ[home]
        if via_a or via_b:
            out.add(r)
    return out


def _counts(s):
    return [list(map(int, row)) for row in s.region_counts]


def _courts(s):
    return [list(map(int, row)) for row in s.courts]


def _supply(s):
    return list(map(int, s.supply))


def _hand(s, p):
    return {c: n for c, n in dict(s.hands[p]).items() if n}


def _conserved(s):
    for f in range(3):
        total = (
            sum(row[f] for row in _counts(s)) + sum(row[f] for row in _courts(s)) + _supply(s)[f]
        )
        assert total == POOL, f"faction {f}: {total} != {POOL}"


def _on_board(s):
    return {follower(r, f) for r, row in enumerate(_counts(s)) for f, n in enumerate(row) if n > 0}


def _targets_after_play(s, card):
    s.apply_action(card)
    return s.legal_actions()


# ---------------------------------------------------------------- R-210


def test_R210_setup_basic_scottish_only_strathclyde():
    """R-210 example: no discs on the board, Scottish Support: eligible = {Strathclyde} (the
    setup_basic scenario's example block)."""
    from kingisdead.scenario import load_scenario

    data = json.loads((SCEN / "setup_basic.json").read_text())
    s = load_scenario(SCEN / "setup_basic.json")
    ex = data["example"]["expect"]
    assert s.legal_actions() == ex["legal_after"]["0"]
    s.apply_action(ex["legal_after"]["0"][1])  # PLAY(1)
    assert s.legal_actions() == [region(1)]
    assert s.current_player() == 0


def test_R210_setup_basic_example_replay():
    """R-210 / R-211: replaying setup_basic's example actions [1, 9] gives the documented
    legal sets, regions and supply."""
    from kingisdead.scenario import load_scenario

    data = json.loads((SCEN / "setup_basic.json").read_text())
    ex = data["example"]
    s = load_scenario(SCEN / "setup_basic.json")
    for i, a in enumerate(ex["actions"]):
        s.apply_action(a)
        key = str(i + 1)
        if key in ex["expect"]["legal_after"]:
            assert s.legal_actions() == ex["expect"]["legal_after"][key]
    assert _counts(s)[1] == [3, 2, 1]
    assert _supply(s) == [3, 3, 4]


@pytest.mark.parametrize(
    "card,expected",
    [(1, {1}), (2, {2, 5, 7}), (3, {3, 5, 7})],
    ids=["scottish", "welsh", "english"],
)
def test_R210_no_discs_targets_are_neighbours_of_home(card, expected):
    """R-210 (b): with no discs on the board, the eligible regions are exactly those bordering
    the home region (Moray/Gwynedd/Essex); the home region itself is not eligible."""
    s = _pos()
    assert _eligible(card - 1, {}) == expected
    assert _targets_after_play(s, card) == sorted(region(r) for r in expected)


@pytest.mark.parametrize("state", ["W", "E", "unstable"])
@pytest.mark.parametrize("card", [1])
def test_R210_closed_home_without_control_leaves_nothing_eligible(card, state):
    """R-210 example: Moray closed by someone else (Welsh/English control or instability) and no
    Scottish-controlled region: Scottish Support has no eligible region; the card is played and
    play moves straight to SUMMON (R-202)."""
    s = _pos(closed={0: state})
    assert _eligible(0, {0: state}) == set()
    legal = _targets_after_play(s, card)
    assert legal and all(a >= 16 for a in legal)
    assert not set(range(0, 16)) & set(legal)


def test_R210_control_makes_home_itself_eligible_via_neighbour():
    """R-210 (a): Scottish control Strathclyde, Moray (home) open: Moray is eligible through (a)
    (it borders a Scottish-controlled region); also Lancaster and Northumbria. Strathclyde itself
    is closed, so not eligible."""
    closed = {1: "S"}
    s = _pos(closed=closed)
    assert _targets_after_play(s, 1) == [region(0), region(2), region(3)]
    assert _eligible(0, closed) == {0, 2, 3}


def test_R210_home_controlled_by_faction_not_via_b():
    """R-210: Moray is Scottish-controlled (closed): rule (b) no longer applies (H not open) but
    (a) makes Strathclyde eligible."""
    s = _pos(closed={0: "S"})
    assert _targets_after_play(s, 1) == [region(1)]


def test_R210_closed_neighbours_are_excluded_open_ones_remain():
    """R-210 / R-200: Welsh control Warwick, Gwynedd (home) unstable: only (a) applies, and only
    open regions qualify: Lancaster, Northumbria, Essex, Devon."""
    closed = {5: "W", 4: "unstable"}
    s = _pos(closed=closed)
    assert _eligible(1, closed) == {2, 3, 6, 7}
    assert _targets_after_play(s, 2) == [region(r) for r in (2, 3, 6, 7)]


def test_R210_other_factions_control_does_not_count():
    """R-210 (negative): English control Lancaster; Scottish Support still uses only rule (b)
    (Moray open): Strathclyde alone."""
    s = _pos(closed={2: "E"})
    assert _targets_after_play(s, 1) == [region(1)]


def test_R210_home_open_and_control_union():
    """R-210: (a) and (b) are a union. English control Devon with Essex open: Essex is eligible
    through (a) (borders Devon); Northumbria, Warwick through (b) (border Essex);
    Gwynedd through (a) (borders Devon)."""
    closed = {7: "E"}
    s = _pos(closed=closed)
    assert _eligible(2, closed) == {3, 4, 5, 6}
    assert _targets_after_play(s, 3) == [region(r) for r in (3, 4, 5, 6)]


def test_R210_cannot_choose_ineligible_region():
    """R-210 (negative): at the target step, REGION of a non-eligible region (Devon for Scottish
    Support) is rejected."""
    s = _pos()
    s.apply_action(1)
    assert region(7) not in s.legal_actions()
    with pytest.raises(Exception):  # noqa: B017
        s.apply_action(region(7))


def test_R210_cannot_choose_closed_region():
    """R-210 / R-200 (negative): a controlled region next to the home region is never offered."""
    s = _pos(closed={1: "W"})
    # Moray open, but Strathclyde closed: nothing eligible for Scottish Support
    legal = _targets_after_play(s, 1)
    assert region(1) not in legal
    assert all(a >= 16 for a in legal)


@pytest.mark.parametrize(
    "closed",
    [
        {},
        {0: "unstable"},
        {1: "S"},
        {1: "S", 0: "W"},
        {6: "E", 3: "S"},
        {4: "W", 5: "W", 2: "unstable"},
        {7: "E", 6: "unstable", 5: "S"},
    ],
)
@pytest.mark.parametrize("card", [1, 2, 3])
def test_R210_mask_equals_eligible_set(card, closed):
    """R-210 / R-200: the SUPPORT_TARGET mask equals the independently computed eligible set; a
    region is never listed unless open. (Empty eligible set -> straight to SUMMON.)"""
    s = _pos(closed=closed)
    elig = _eligible(card - 1, closed)
    assert not elig & set(closed)
    legal = _targets_after_play(s, card)
    if elig:
        assert legal == sorted(region(r) for r in elig)
    else:
        assert legal and all(a >= 16 for a in legal)


# ---------------------------------------------------------------- R-211


@pytest.mark.parametrize("card", [1, 2, 3])
def test_R211_places_two_followers_of_the_cards_faction_in_chosen_region(card):
    """R-211: choosing an eligible region places 2 followers of F from the supply there; the
    supply of F falls by 2, other factions' supply is untouched."""
    f = card - 1
    s = _pos(supply={0: 5, 1: 5, 2: 5})
    target = sorted(_eligible(f, {}))[0]
    before, sup = _counts(s), _supply(s)
    s.apply_action(card)
    s.apply_action(region(target))
    after = _counts(s)
    assert after[target][f] == before[target][f] + 2
    for r in range(8):
        if r != target:
            assert after[r] == before[r]
    assert [after[target][g] for g in range(3) if g != f] == [
        before[target][g] for g in range(3) if g != f
    ]
    exp = list(sup)
    exp[f] -= 2
    assert _supply(s) == exp
    _conserved(s)


def test_R211_both_go_to_same_region():
    """R-211: the two followers are not split; exactly one region changes."""
    s = _pos()
    before = _counts(s)
    s.apply_action(1)
    s.apply_action(region(1))
    changed = [r for r in range(8) if _counts(s)[r] != before[r]]
    assert changed == [1]


def test_R211_supply_of_one_places_one():
    """R-211 example: supply holds 1 Welsh follower: Welsh Support places that one follower."""
    s = _pos(supply={1: 1})
    before = _counts(s)
    s.apply_action(2)
    assert region(2) in s.legal_actions()  # target step is still offered
    s.apply_action(region(2))
    assert _counts(s)[2][1] == before[2][1] + 1
    assert _supply(s)[1] == 0
    _conserved(s)


def test_R211_supply_exactly_two_places_two():
    """R-211 boundary: supply of exactly 2 places 2 and empties the supply."""
    s = _pos(supply={2: 2})
    before = _counts(s)
    s.apply_action(3)
    s.apply_action(region(3))
    assert _counts(s)[3][2] == before[3][2] + 2
    assert _supply(s)[2] == 0


@pytest.mark.parametrize("card", [1, 2, 3])
def test_R211_empty_supply_means_no_target_step(card):
    """R-211 / ACTIONS 4: supply of F is 0: no region is chosen; the card has no effect and play
    goes to SUMMON (only FOLLOWER ids, no REGION ids)."""
    f = card - 1
    s = _pos(supply={f: 0})
    before = _counts(s)
    legal = _targets_after_play(s, card)
    assert legal and all(a >= 16 for a in legal)
    assert _counts(s) == before
    assert s.current_player() == 0
    _conserved(s)


def test_R211_empty_supply_of_other_faction_does_not_matter():
    """R-211 (negative): Welsh supply empty does not stop Scottish Support from needing a target."""
    s = _pos(supply={1: 0})
    assert _targets_after_play(s, 1) == [region(1)]


def test_R211_no_eligible_region_means_no_effect():
    """R-211: no eligible region: nothing is placed, supply unchanged, straight to SUMMON."""
    s = _pos(closed={0: "unstable"})
    sup = _supply(s)
    legal = _targets_after_play(s, 1)
    assert all(a >= 16 for a in legal)
    assert _supply(s) == sup


def test_R211_added_followers_are_in_an_open_region():
    """R-211 / R-200: after placing, the closed regions still hold no followers."""
    closed = {5: "W", 4: "unstable"}
    s = _pos(closed=closed)
    s.apply_action(2)
    s.apply_action(region(6))
    for r in closed:
        assert _counts(s)[r] == [0, 0, 0]


# ---------------------------------------------------------------- R-201


def test_R201_summon_options_are_present_region_faction_pairs():
    """R-201: after the Support placement the mask is exactly FOLLOWER(r, f) for each (region,
    faction) present on the board (including the just-placed ones; no PASS or PLAY ids)."""
    s = _pos(regions={0: {0: 2}, 1: {1: 1, 2: 3}, 6: {2: 1}}, supply={0: 3})
    s.apply_action(1)
    s.apply_action(region(1))
    assert s.legal_actions() == sorted(_on_board(s))
    assert follower(1, 0) in s.legal_actions()  # the new Scots
    assert follower(0, 1) not in s.legal_actions()  # no Welsh in Moray
    assert follower(2, 0) not in s.legal_actions()  # nobody in Lancaster
    assert s.current_player() == 0


def test_R201_summon_moves_one_follower_from_region_to_own_court():
    """R-201: summon moves one follower of the chosen faction from that region to the acting
    player's court only; supply and the other court are unchanged."""
    s = _pos()
    s.apply_action(1)
    s.apply_action(region(1))
    board, courts, sup = _counts(s), _courts(s), _supply(s)
    s.apply_action(follower(4, 1))
    nb, nc = _counts(s), _courts(s)
    assert nb[4][1] == board[4][1] - 1
    assert nc[0][1] == courts[0][1] + 1
    assert nc[1] == courts[1]
    assert _supply(s) == sup
    for r in range(8):
        if r != 4:
            assert nb[r] == board[r]
    _conserved(s)


def test_R201_need_not_be_from_touched_region_or_same_faction():
    """R-201: the summoned follower may come from any region and any faction, not just the
    region the card touched: Support into Strathclyde, summon English from Devon."""
    s = _pos()
    s.apply_action(1)
    s.apply_action(region(1))
    assert follower(7, 2) in s.legal_actions()
    s.apply_action(follower(7, 2))
    assert _courts(s)[0][2] == 1


def test_R201_summon_is_mandatory_when_board_has_followers():
    """R-201 (negative): while a follower is on a region the summon cannot be skipped: PASS (0)
    is not legal in the SUMMON step."""
    s = _pos()
    s.apply_action(1)
    s.apply_action(region(1))
    assert PASS not in s.legal_actions()


def test_R201_after_summon_turn_returns_to_next_seat_at_turn_start():
    """R-201 / ACTIONS 4: after the summon, TURN_START for the next seat: PASS and the cards the
    next player still holds (all seven)."""
    s = _pos()
    s.apply_action(1)
    s.apply_action(region(1))
    s.apply_action(follower(0, 0))
    assert s.current_player() == 1
    assert s.legal_actions() == [0, 1, 2, 3, 4, 5, 6, 7]
    assert not s.is_terminal()


def test_R201_summon_options_exclude_closed_regions_and_court_followers():
    """R-201 (negative): followers in courts or supply are never summonable, closed regions hold
    none. Only open regions with followers appear."""
    closed = {0: "S"}
    s = _pos(closed=closed, regions={1: {0: 1}, 2: {1: 1}})
    s.apply_action(2)
    # Welsh Support: Gwynedd open, Lancaster has a follower -> target
    s.apply_action(region(2))
    legal = s.legal_actions()
    assert legal == sorted(_on_board(s))
    assert not any(16 <= a < 19 for a in legal)  # Moray (closed)


def test_R201_summon_skipped_when_board_empty():
    """R-201: no follower on any region: the summon is skipped and the turn passes straight on.
    Scottish Support with an empty supply on an empty board has no effect and no summon."""
    s = _pos(regions={}, supply={0: 0})
    s.apply_action(1)
    assert s.current_player() == 1
    assert s.legal_actions() == [0, 1, 2, 3, 4, 5, 6, 7]
    assert _hand(s, 0) == {c: n for c, n in START_HAND.items() if c != 1}


def test_R201_single_follower_board_has_one_summon_choice():
    """R-201: with exactly one follower on the board and no placement, only that (region, faction)
    is offered; after summoning, the board is empty and play passes on."""
    s = _pos(regions={2: {1: 1}}, supply={0: 0})
    s.apply_action(1)  # Scottish supply 0: no effect
    assert s.legal_actions() == [follower(2, 1)]
    s.apply_action(follower(2, 1))
    assert _counts(s)[2] == [0, 0, 0]
    assert _courts(s)[0] == [0, 1, 0]
    assert s.current_player() == 1


def test_R201_pass_is_not_followed_by_summon():
    """R-201: summon never follows a pass; a pass goes straight to the next seat's TURN_START."""
    s = _pos()
    s.apply_action(PASS)
    assert s.current_player() == 1
    assert s.legal_actions() == [0, 1, 2, 3, 4, 5, 6, 7]


# ---------------------------------------------------------------- R-202


def test_R202_ineffective_support_is_still_played_and_summons():
    """R-202: Support with no eligible region is still played (hand decrements, play recorded,
    pass count reset) and the summon still happens."""
    s = _pos(closed={0: "unstable"}, pass_count=1)
    s.apply_action(1)
    assert all(a >= 16 for a in s.legal_actions())  # summon follows
    assert _hand(s, 0) == {c: n for c, n in START_HAND.items() if c != 1}
    assert s.plays_total == 1
    assert s.pass_count == 0
    s.apply_action(s.legal_actions()[0])
    assert s.current_player() == 1
    _conserved(s)


def test_R202_support_with_empty_supply_is_still_played_and_summons():
    """R-202: Support with an empty supply of F: card played, summon happens."""
    s = _pos(supply={2: 0})
    s.apply_action(3)
    assert s.legal_actions() and all(a >= 16 for a in s.legal_actions())
    assert 3 not in _hand(s, 0)
    s.apply_action(s.legal_actions()[0])
    assert s.current_player() == 1


def test_R202_partial_support_with_one_follower_then_summon():
    """R-202 / R-211: supply of 1 is a partial action: place one, then summon, then next seat."""
    s = _pos(supply={0: 1})
    s.apply_action(1)
    s.apply_action(region(1))
    assert _supply(s)[0] == 0
    s.apply_action(follower(1, 0))
    assert s.current_player() == 1
    _conserved(s)


def test_R202_ineffective_card_can_still_be_played_by_both_players():
    """R-202 / R-101: after the first player burned Scottish Support with no effect, the other
    seat still has it available."""
    s = _pos(supply={0: 0})
    s.apply_action(1)
    s.apply_action(s.legal_actions()[0])
    assert 1 in s.legal_actions()  # seat 1 still holds Scottish Support


# ---------------------------------------------------------------- bookkeeping


def test_R102_support_play_decrements_hand_and_resets_pass_count():
    """R-102 / R-104 via Support: after Support and summon, hand has 7 cards, plays_total is 1,
    the pass count is 0, the other hand is untouched."""
    s = _pos(pass_count=1)
    s.apply_action(1)
    s.apply_action(region(1))
    s.apply_action(follower(1, 0))
    assert sum(_hand(s, 0).values()) == 7 and 1 not in _hand(s, 0)
    assert _hand(s, 1) == START_HAND
    assert s.pass_count == 0
    assert s.plays_total == 1


@pytest.mark.parametrize("card", [1, 2, 3])
def test_R015_conservation_after_every_support_step(card):
    """R-015: follower conservation holds after the play, the target and the summon."""
    s = _pos(closed={7: "unstable"})
    _conserved(s)
    s.apply_action(card)
    _conserved(s)
    if s.legal_actions()[0] < 16:
        s.apply_action(s.legal_actions()[0])
        _conserved(s)
    s.apply_action(s.legal_actions()[0])
    _conserved(s)
