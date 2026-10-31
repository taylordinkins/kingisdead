"""Invariant checker tests (Phase 2 unit 11b): ``tests/support/invariants.py``.

``check_invariants(state)`` must raise ``InvariantViolation`` (an ``AssertionError`` subclass) on
the first violated invariant and return quietly on a valid state. Every test is
``pending("R-015")`` until the module exists. The module is imported lazily so that this file
collects before it exists.

Assumed state attributes (corrupted directly; values are replaced by plain lists/dicts, so the
checker must accept lists, tuples and numpy arrays alike):
  region_counts[r][f]    followers on region r          courts[p][f], supply[f]
  region_states[r]       kingisdead.constants.REGION_OPEN / REGION_CONTROLLED / REGION_UNSTABLE
  region_control[r]      faction index of the controller; None or -1 when none
  slot_regions[i]        region on the card in slot i+1 (all 8 set after setup)
  struggles_resolved     int          pass_count   int        plays_total   int
  hands[p]               dict card id (1..7) -> copies        negotiation_discs[p]  region or None
  recent_win[f]          struggle number 1..8 or -1
  returns() / legal_actions() / is_terminal()  (patched on the instance for node-level checks)
Not tested as corruptions (impossible to reach with 8 regions): "more than 8 control discs".
Not tested: "negotiation disc on face-up cards only" - it conflicts with SCENARIOS V6 (a disc
card may later be face down); see the report.
"""

import copy
import random

import pyspiel
import pytest

import kingisdead.game  # noqa: F401
from kingisdead.scenario import load_scenario

from .test_scenario_loader import REGIONS, SCEN, _hand


def _mod():
    from tests.support import invariants

    return invariants


def check(s):
    _mod().check_invariants(s)


def violates(s):
    with pytest.raises(_mod().InvariantViolation):
        _mod().check_invariants(s)


def _c():
    from kingisdead import constants

    return constants


def _lists(x):
    if isinstance(x, dict):
        return {k: _lists(v) for k, v in x.items()}
    if isinstance(x, str | bytes) or x is None:
        return x
    try:
        return [_lists(v) for v in x]
    except TypeError:
        return int(x) if hasattr(x, "__int__") and not isinstance(x, bool) else x


def edit(s, attr, fn):
    """Replace ``s.attr`` by a mutable list copy and apply ``fn`` to it."""
    v = _lists(getattr(s, attr))
    fn(v)
    setattr(s, attr, v)


def set_scalar(s, attr, val):
    setattr(s, attr, val)


# ---------------------------------------------------------------- fixtures


def _scn(**over):
    d = {
        "format": 1,
        "kind": "state",
        "players": 2,
        "slots": list(REGIONS),
        "regions": {},
        "courts": [{"S": 1}, {"E": 1}],
    }
    d.update(over)
    return copy.deepcopy(d)


def rich():
    """2p: slots 1..3 closed (S, unstable, unstable), followers on open regions, both players have
    played one card, P0's Negotiate disc on Devon (face up), P1's hand lacks Manoeuvre."""
    return load_scenario(
        _scn(
            struggles=3,
            region_state={"Moray": "S", "Strathclyde": "unstable", "Lancaster": "unstable"},
            regions={"Gwynedd": {"S": 1, "W": 2}, "Warwick": {"E": 2}},
            hands=[_hand("negotiate"), _hand("manoeuvre")],
            negotiation=["Devon", None],
            last_play=[1, 2],
            last_card={"type": "manoeuvre"},
            pass_count=1,
            to_play=0,
        )
    )


def fresh2():
    return load_scenario(str(SCEN / "setup_basic.json"))


def midgame():
    return load_scenario(str(SCEN / "undo_block_outmanoeuvre.json"))


def terminal3():
    return load_scenario(str(SCEN / "coronation_tiebreak.json"))


def invasion():
    return load_scenario(
        _scn(
            struggles=3,
            region_state={"Moray": "unstable", "Strathclyde": "unstable", "Lancaster": "unstable"},
        )
    )


def three_player():
    return load_scenario(
        {
            "format": 1,
            "kind": "state",
            "players": 3,
            "slots": list(REGIONS),
            "regions": {"Strathclyde": {"S": 3, "W": 1}},
            "courts": [{"S": 1}, {"W": 2}, {}],
            "struggles": 1,
            "region_state": {"Moray": "W"},
            "pass_count": 2,
            "to_play": 2,
        }
    )


VALID = [fresh2, midgame, rich, terminal3, invasion, three_player]


# ---------------------------------------------------------------- valid states pass


@pytest.mark.parametrize("make", VALID, ids=lambda f: f.__name__)
def test_R015_valid_scenarios_pass(make):
    """R-015 and the listed invariants: untouched valid scenario states raise nothing."""
    check(make())


def test_R015_violation_is_an_assertion_error():
    """InvariantViolation subclasses AssertionError and carries a message."""
    mod = _mod()
    assert issubclass(mod.InvariantViolation, AssertionError)
    s = rich()
    s.supply = [99, 0, 0]
    with pytest.raises(AssertionError, match=r"\S"):
        mod.check_invariants(s)


def _playout_states(n, seed, limit=400):
    game = pyspiel.load_game(f"python_king_is_dead(players={n})")
    rng = random.Random(seed)
    s = game.new_initial_state()
    steps = 0
    while not s.is_terminal() and steps < limit:
        if s.is_chance_node():
            acts, probs = zip(*s.chance_outcomes(), strict=True)
            s.apply_action(rng.choices(acts, probs)[0])
        else:
            s.apply_action(rng.choice(s.legal_actions()))
            yield s
        steps += 1
    if s.is_terminal():
        yield s


@pytest.mark.parametrize("n,seed", [(2, 1), (2, 2), (3, 3), (3, 4)])
def test_R015_random_playouts_pass_after_every_action(n, seed):
    """R-015: every post-setup state of a random playout satisfies all invariants (including the
    terminal one: no legal actions, returns sum to 0)."""
    count = 0
    for s in _playout_states(n, seed):
        check(s)
        count += 1
    assert count > 10


# ---------------------------------------------------------------- R-015 conservation


@pytest.mark.parametrize("f", [0, 1, 2])
def test_R015_extra_follower_in_supply_violates(f):
    """R-015: a follower created in the supply breaks conservation of that faction."""
    s = rich()
    edit(s, "supply", lambda v: v.__setitem__(f, v[f] + 1))
    violates(s)


def test_R015_missing_follower_in_region_violates():
    """R-015: a follower deleted from a region."""
    s = rich()
    edit(s, "region_counts", lambda v: v[4].__setitem__(1, v[4][1] - 1))
    violates(s)


def test_R015_follower_added_to_court_violates():
    """R-015: a follower added to a court."""
    s = rich()
    edit(s, "courts", lambda v: v[1].__setitem__(0, v[1][0] + 1))
    violates(s)


def test_R015_negative_supply_with_balanced_total_violates():
    """R-015/R-005: negative counts are invalid even if totals balance."""
    s = rich()

    def f(v):
        v[0] = -1
        v[1] += 1

    edit(s, "supply", f)
    # supply S -1 and W +1 does not balance per faction; make S balance via a region instead
    edit(s, "region_counts", lambda v: v[4].__setitem__(0, v[4][0] + 1))
    violates(s)


def test_R015_three_player_pool_is_18():
    """R-015/R-005: 3p pool is 18; one extra in a 3p supply violates, and the 2p pool of 16 is
    not what is checked in 3p."""
    s = three_player()
    check(s)
    edit(s, "supply", lambda v: v.__setitem__(2, v[2] + 1))
    violates(s)


# ---------------------------------------------------------------- followers only on open regions


@pytest.mark.parametrize("region", [0, 1, 2], ids=["controlled", "unstable_a", "unstable_b"])
def test_R015_follower_on_closed_region_violates(region):
    """R-015/R-200: a follower moved from the supply onto a closed region."""
    s = rich()

    def reg(v):
        v[region][0] += 1

    edit(s, "region_counts", reg)
    edit(s, "supply", lambda v: v.__setitem__(0, v[0] - 1))
    violates(s)


# ---------------------------------------------------------------- R-004 region-state consistency


def test_R004_controlled_region_without_controller_violates():
    """R-004: a controlled region must have a controlling faction."""
    s = rich()
    edit(s, "region_control", lambda v: v.__setitem__(0, None))
    violates(s)


@pytest.mark.parametrize("region", [1, 4], ids=["unstable", "open"])
def test_R004_unstable_or_open_region_with_controller_violates(region):
    """R-004: unstable and open regions have no controlling faction."""
    s = rich()
    edit(s, "region_control", lambda v: v.__setitem__(region, 1))
    violates(s)


def test_R004_third_unstable_region_in_nonterminal_state_violates():
    """R-004/R-304: 3 instability discs on the board only at a terminal state."""
    s = rich()
    assert not s.is_terminal()
    c = _c()
    edit(s, "region_states", lambda v: v.__setitem__(3, c.REGION_UNSTABLE))
    violates(s)


def test_R006_more_than_three_unstable_violates():
    """R-006: only 3 instability discs exist; four unstable regions violate even at terminal."""
    s = invasion()
    check(s)
    c = _c()
    edit(s, "region_states", lambda v: v.__setitem__(3, c.REGION_UNSTABLE))
    violates(s)


def test_R004_valid_invasion_terminal_passes():
    """R-004/R-304: exactly 3 unstable at a terminal state is valid."""
    check(invasion())


# ---------------------------------------------------------------- slots / struggles


def test_R010_slot_regions_not_a_permutation_violates():
    """R-010: slot_regions is a permutation of 0..7 after setup (duplicate region)."""
    s = rich()
    edit(s, "slot_regions", lambda v: v.__setitem__(6, v[7]))
    violates(s)


def test_R010_slot_region_out_of_range_violates():
    """R-010: a region index outside 0..7."""
    s = rich()
    edit(s, "slot_regions", lambda v: v.__setitem__(7, 8))
    violates(s)


def test_R303_struggles_not_matching_closed_regions_violates():
    """R-300/R-303: slots 1..struggles_resolved must be exactly the closed regions."""
    s = rich()
    set_scalar(s, "struggles_resolved", s.struggles_resolved + 1)
    violates(s)
    s = rich()
    set_scalar(s, "struggles_resolved", s.struggles_resolved - 1)
    violates(s)


def test_R303_closed_regions_not_in_contest_order_violates():
    """R-303: a closed region sitting outside slots 1..k (swap slot 3 and slot 7 cards)."""
    s = rich()
    edit(
        s, "slot_regions", lambda v: v.__setitem__(slice(None), [*v[:2], v[6], *v[3:6], v[2], v[7]])
    )
    violates(s)


def test_R303_struggles_above_eight_violates():
    """R-303: struggles_resolved <= 8."""
    s = terminal3()
    set_scalar(s, "struggles_resolved", 9)
    violates(s)


# ---------------------------------------------------------------- hands / plays


def test_R008_hand_with_nine_cards_violates():
    """R-008: a hand never holds more than 8 cards."""
    s = fresh2()
    edit(s, "hands", lambda v: v[0].__setitem__(1, v[0].get(1, 0) + 1))
    violates(s)


def test_R008_hand_size_not_matching_plays_violates():
    """R-008: sum(hand) = 8 - cards played; a card vanishing without a play breaks it."""
    s = midgame()
    check(s)
    edit(s, "hands", lambda v: v[1].__setitem__(1, v[1][1] - 1))
    violates(s)


def test_R008_assemble_more_than_two_copies_violates():
    """R-008: at most 2 copies of Assemble (a hand with 3 while holding 8 total)."""
    s = fresh2()

    def f(v):
        v[0][4] = 3
        v[0][1] = 0  # still 8 cards

    edit(s, "hands", f)
    violates(s)


def test_R008_negative_copies_violates():
    """R-008: a negative copy count is invalid even if the sum matches."""
    s = fresh2()

    def f(v):
        v[0][1] = -1
        v[0][4] = 4  # 8 cards in total

    edit(s, "hands", f)
    violates(s)


def test_R102_plays_total_not_matching_hands_violates():
    """R-102: plays_total equals the sum over players of (8 - hand size)."""
    s = midgame()
    set_scalar(s, "plays_total", s.plays_total + 1)
    violates(s)
    s = midgame()
    set_scalar(s, "plays_total", s.plays_total - 1)
    violates(s)


# ---------------------------------------------------------------- negotiation discs


def test_R006_two_discs_on_same_region_violates():
    """R-006: spent discs are on distinct regions."""
    s = rich()
    edit(s, "negotiation_discs", lambda v: [v.__setitem__(0, 7), v.__setitem__(1, 7)])
    violates(s)


def test_R006_disc_on_nonexistent_region_violates():
    """R-006: a disc names a region 0..7 or None."""
    s = rich()
    edit(s, "negotiation_discs", lambda v: v.__setitem__(1, 8))
    violates(s)


def test_R006_wrong_number_of_discs_violates():
    """R-006: one negotiation disc per player (a third slot for a 2p game)."""
    s = rich()
    edit(s, "negotiation_discs", lambda v: v.append(None))
    violates(s)


# ---------------------------------------------------------------- pass count


@pytest.mark.parametrize("bad", [-1, 2, 5])
def test_R103_pass_count_out_of_range_violates_2p(bad):
    """R-103: pass_count in 0..n-1 (n = 2)."""
    s = rich()
    set_scalar(s, "pass_count", bad)
    violates(s)


def test_R103_pass_count_boundary_values_pass():
    """R-103: 0 and n-1 are valid (2p and 3p)."""
    s = rich()
    for v in (0, 1):
        set_scalar(s, "pass_count", v)
        check(s)
    s = three_player()
    for v in (0, 1, 2):
        set_scalar(s, "pass_count", v)
        check(s)
    set_scalar(s, "pass_count", 3)
    violates(s)


# ---------------------------------------------------------------- recent win


def test_R303_recent_win_duplicate_struggle_violates():
    """R-303: recent_win values are distinct struggle numbers (one struggle has one winner)."""
    s = midgame()
    edit(s, "recent_win", lambda v: [v.__setitem__(0, 1), v.__setitem__(1, 1)])
    violates(s)


def test_R303_recent_win_out_of_range_violates():
    """R-303: a recent win is -1 or a struggle number 1..struggles_resolved."""
    s = rich()
    check(s)
    for bad in (9, -2, 0):
        t = rich()
        edit(t, "recent_win", lambda v, b=bad: v.__setitem__(1, b))
        violates(t)
    t = rich()
    edit(t, "recent_win", lambda v: v.__setitem__(1, 4))  # only 3 struggles resolved
    violates(t)


def test_R303_all_minus_one_recent_wins_not_duplicates():
    """R-303: several -1 entries are fine (no win yet)."""
    check(fresh2())
    check(midgame())


# ---------------------------------------------------------------- returns and legal actions


def test_R405_nonterminal_returns_must_be_zero():
    """R-405: returns are zero at non-terminal states."""
    s = rich()
    s.returns = lambda: [0.5, -0.5]
    violates(s)


def test_R405_terminal_returns_must_sum_to_zero():
    """R-405: returns sum to 0 at a terminal state."""
    s = terminal3()
    s.returns = lambda: [1.0, 1.0, -0.5]
    violates(s)


def test_R101_nonterminal_decision_node_needs_legal_actions():
    """R-101: legal actions are non-empty at a non-terminal decision node."""
    s = rich()
    s.legal_actions = lambda *a: []
    violates(s)


def test_R304_terminal_has_no_legal_actions():
    """R-304: legal actions are empty at a terminal state."""
    s = terminal3()
    s.legal_actions = lambda *a: [0]
    violates(s)
