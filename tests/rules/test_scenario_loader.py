"""Scenario loader tests (Phase 2 unit 11a): docs/SCENARIOS.md sections 1-5.

Covers what the other rule tests only exercise indirectly: every shipped scenario loads and its
``example`` block replays; every validation rule V1..V11 rejects a bad scenario and accepts the
boundary case; ``setup`` vs ``state`` kinds; 2 and 3 players; pickle round-trip.

Assumptions (flagged in the report):
  * ``load_scenario(path_or_dict)`` returns a state, raising ``ValueError`` for a rejected scenario.
  * The error message names the failing rule: either ``V<n>`` or one of the R-IDs SCENARIOS.md
    lists next to that rule (SCENARIOS.md only says "with the failing rule").
  * State attributes as in the other rule tests: region_counts[r][f], supply[f];
    region index order is the R-001 order (Moray .. Devon).
  * The phase is read from ``s.phase`` if it is a name or enum (it is a bare int today),
    otherwise only SUMMON / TURN_START are inferred from the legal actions (ACTIONS.md section 4).
"""

import copy
import json
import pickle
import re
from pathlib import Path

import pytest

import kingisdead.game  # noqa: F401  (registers the game)
from kingisdead.scenario import load_scenario

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
FN = ["S", "W", "E"]
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
RULE_IDS = {
    1: ("R-005",),
    2: ("R-004", "R-302"),
    3: ("R-304",),
    4: ("R-300", "R-303"),
    5: ("R-303", "R-004"),
    6: ("R-006", "R-213"),
    7: ("R-102", "R-401"),
    8: ("R-008",),
    9: ("R-103",),
    10: ("R-102", "R-216"),
    11: ("R-011", "R-012", "R-013", "R-014"),
}
SCEN_FILES = sorted(SCEN.glob("*.json"))


# ---------------------------------------------------------------- builders


def _hand(*remove):
    h = list(FULL_HAND)
    for c in remove:
        h.remove(c)
    return h


def _state(players=2, **over):
    """A valid empty-board ``state`` scenario dict, with ``over`` merged on top."""
    d = {
        "format": 1,
        "kind": "state",
        "players": players,
        "slots": list(REGIONS),
        "regions": {},
        "courts": [{} for _ in range(players)],
    }
    d.update(over)
    return d


def _setup(players=2):
    d = {
        "format": 1,
        "kind": "setup",
        "players": players,
        "slots": list(REGIONS),
        "regions": {
            "Moray": {"S": 2, "W": 1, "E": 1},
            "Strathclyde": {"S": 1, "W": 2, "E": 1},
            "Lancaster": {"S": 1, "W": 1, "E": 2},
            "Northumbria": {"S": 1, "W": 1, "E": 2},
            "Gwynedd": {"S": 1, "W": 2, "E": 1},
            "Warwick": {"S": 1, "W": 1, "E": 2},
            "Essex": {"S": 1, "W": 1, "E": 2},
            "Devon": {"S": 1, "W": 2, "E": 1},
        },
        "courts": [{"S": 1, "W": 1}, {"E": 2}, {"S": 1, "E": 1}][:players],
    }
    return d


def _load(d):
    return load_scenario(copy.deepcopy(d))


def _rejected(d, v):
    """The scenario is rejected with a ValueError naming rule V<v> (or its R-IDs)."""
    with pytest.raises(ValueError) as ei:
        _load(d)
    msg = str(ei.value)
    names = [f"V{v}", *RULE_IDS[v]]
    assert any(re.search(rf"\b{re.escape(n)}\b", msg) for n in names), (
        f"message does not name V{v} or {RULE_IDS[v]}: {msg!r}"
    )


def _rejected_any(d):
    with pytest.raises(ValueError):
        _load(d)


def _counts(s):
    return [[int(x) for x in row] for row in s.region_counts]


def _phase_ok(s, name):
    ph = getattr(s, "phase", None)
    if ph is not None and not isinstance(ph, int):
        return str(getattr(ph, "name", ph)).split(".")[-1] == name
    legal = s.legal_actions()
    if name == "SUMMON":
        return bool(legal) and all(a >= 16 for a in legal)
    if name == "TURN_START":
        return 0 in legal
    pytest.skip(f"cannot infer phase {name} without a state attribute")


# ---------------------------------------------------------------- shipped scenarios


@pytest.mark.parametrize("path", SCEN_FILES, ids=lambda p: p.name)
def test_shipped_scenario_loads_and_example_replays(path):
    """SCENARIOS 4/5: every scenario file loads and its example block (actions, legal_after,
    regions, supply, phase, terminal, winners, returns) holds."""
    data = json.loads(path.read_text())
    s = load_scenario(str(path))
    assert not s.is_chance_node()
    ex = data.get("example")
    if ex is None:
        return
    exp = ex.get("expect", {})
    legal_after = {int(k): v for k, v in exp.get("legal_after", {}).items()}
    actions = ex["actions"]
    if 0 in legal_after:
        assert sorted(s.legal_actions()) == legal_after[0]
    for i, a in enumerate(actions, start=1):
        assert a in s.legal_actions(), f"action {a} (#{i}) not legal in {path.name}"
        s.apply_action(a)
        if i in legal_after:
            assert sorted(s.legal_actions()) == sorted(legal_after[i]), f"after {i} actions"
    cnt = _counts(s)
    for region, cm in exp.get("regions", {}).items():
        got = dict(zip(FN, cnt[REGIONS.index(region)], strict=True))
        assert got == {f: cm.get(f, 0) for f in FN}, region
    for f, n in exp.get("supply", {}).items():
        assert int(s.supply[FN.index(f)]) == n, f"supply {f}"
    if "phase" in exp:
        assert _phase_ok(s, exp["phase"])
    if "terminal" in exp:
        assert s.is_terminal() == exp["terminal"]
    if "returns" in exp:
        assert [float(x) for x in s.returns()] == pytest.approx(exp["returns"])
    if "winners" in exp:
        r = [float(x) for x in s.returns()]
        assert [i for i, x in enumerate(r) if x > 0] == exp["winners"]


def test_shipped_scenarios_exist_and_are_json():
    """SCENARIOS 5: the four shipped scenarios are present and parse."""
    names = {p.name for p in SCEN_FILES}
    assert {
        "setup_basic.json",
        "undo_block_outmanoeuvre.json",
        "undo_block_void.json",
        "coronation_tiebreak.json",
    } <= names


def test_load_accepts_path_object_string_and_dict_equally():
    """SCENARIOS/loader: path (str or Path) and parsed dict give the same position."""
    p = SCEN / "undo_block_outmanoeuvre.json"
    a = load_scenario(str(p))
    b = load_scenario(json.loads(p.read_text()))
    assert _counts(a) == _counts(b)
    assert a.legal_actions() == b.legal_actions()
    assert a.current_player() == b.current_player()


def test_load_does_not_mutate_input_dict():
    """Loader hygiene: the caller's dict is left unchanged."""
    d = _state(hands=[_hand(), _hand()])
    before = copy.deepcopy(d)
    load_scenario(d)
    assert d == before


# ---------------------------------------------------------------- kinds and player counts


@pytest.mark.parametrize("players", [2, 3])
def test_setup_kind_loads_to_a_fresh_position(players):
    """SCENARIOS 1, R-014: a valid setup scenario gives the R-014 position (no card played,
    player 0 to act, full hands, no struggle)."""
    s = _load(_setup(players))
    assert not s.is_chance_node()
    assert s.current_player() == 0
    assert s.struggles_resolved == 0 and s.plays_total == 0 and s.pass_count == 0
    assert sorted(s.legal_actions()) == [0, *range(1, 8)]
    cnt = _counts(s)
    assert cnt[REGIONS.index("Moray")] == [2, 1, 1]
    # followers in courts match the scenario
    assert [int(x) for x in s.courts[0]] == [1, 1, 0]


@pytest.mark.parametrize("players", [2, 3])
def test_setup_supply_is_pool_minus_board_minus_courts(players):
    """SCENARIOS 1 (derived supply), R-005: S pool 16/18 less regions and courts."""
    d = _setup(players)
    s = _load(d)
    pool = {2: 16, 3: 18}[players]
    for fi, f in enumerate(FN):
        used = sum(r.get(f, 0) for r in d["regions"].values()) + sum(
            c.get(f, 0) for c in d["courts"]
        )
        assert int(s.supply[fi]) == pool - used


@pytest.mark.parametrize("players", [2, 3])
def test_state_kind_defaults(players):
    """SCENARIOS 1 defaults for kind state: to_play 0, struggles 0, all regions open, full hands,
    pass_count 0, empty record."""
    s = _load(_state(players))
    assert s.current_player() == 0
    assert s.struggles_resolved == 0 and s.plays_total == 0 and s.pass_count == 0
    assert sorted(s.legal_actions()) == [0, *range(1, 8)]
    assert all(h is None for h in s.negotiation_discs)
    pool = {2: 16, 3: 18}[players]
    assert [int(x) for x in s.supply] == [pool] * 3


@pytest.mark.parametrize("players", [2, 3])
def test_state_to_play_selects_player(players):
    """SCENARIOS 1: to_play (0..players-1) is the player to act."""
    for p in range(players):
        assert _load(_state(players, to_play=p)).current_player() == p


def test_state_to_play_out_of_range_rejected():
    """SCENARIOS 1: to_play must be in 0..players-1."""
    _rejected_any(_state(2, to_play=2))
    _rejected_any(_state(3, to_play=3))
    _rejected_any(_state(2, to_play=-1))


def test_setup_kind_rejects_state_only_fields():
    """SCENARIOS 1: a setup scenario may use only the listed fields (to_play, struggles, hands ...
    are state-only)."""
    for key, val in [("to_play", 1), ("struggles", 0), ("pass_count", 0), ("hands", [_hand()] * 2)]:
        d = _setup()
        d[key] = val
        _rejected_any(d)


def test_unknown_keys_rejected():
    """SCENARIOS 1: unknown keys (top level, count map) are an error."""
    d = _state()
    d["bogus"] = 1
    _rejected_any(d)
    d = _state(regions={"Moray": {"X": 1}})
    _rejected_any(d)
    d = _state(regions={"Atlantis": {"S": 1}})
    _rejected_any(d)


def test_header_validation():
    """SCENARIOS 1: format must be 1, kind setup|state, players 2 or 3, slots a permutation of
    the 8 regions, one court per player."""
    _rejected_any(_state(format=2))
    _rejected_any(_state(kind="other"))
    _rejected_any(_state(players=4, courts=[{}] * 4))
    _rejected_any(_state(players=1, courts=[{}]))
    d = _state()
    d["slots"] = REGIONS[:7] + ["Moray"]
    _rejected_any(d)
    d = _state()
    d["slots"] = REGIONS[:7]
    _rejected_any(d)
    _rejected_any(_state(2, courts=[{}]))
    _rejected_any(_state(2, courts=[{}, {}, {}]))
    d = _state()
    del d["courts"]
    _rejected_any(d)


# ---------------------------------------------------------------- V1


def test_V1_boundary_pool_accepted():
    """V1 (R-005): exactly the pool (16 in 2p, 18 in 3p) is accepted, supply 0."""
    s = _load(_state(2, courts=[{"S": 10}, {"S": 3}], regions={"Moray": {"S": 3}}))
    assert int(s.supply[0]) == 0
    s = _load(_state(3, courts=[{"W": 18}, {}, {}]))
    assert int(s.supply[1]) == 0


def test_V1_over_pool_rejected():
    """V1: one over the pool is rejected (courts only, regions+courts, 3p)."""
    _rejected(_state(2, courts=[{"S": 17}, {}]), 1)
    _rejected(_state(2, courts=[{"E": 10}, {"E": 6}], regions={"Moray": {"E": 1}}), 1)
    _rejected(_state(3, courts=[{"W": 19}, {}, {}]), 1)
    _rejected(_state(3, courts=[{"S": 9}, {"S": 9}, {}], regions={"Devon": {"S": 1}}), 1)


def test_V1_pool_is_per_player_count():
    """V1/R-005: 17 of a faction is fine in 3p but not in 2p."""
    _load(_state(3, courts=[{"E": 17}, {}, {}]))
    _rejected(_state(2, courts=[{"E": 17}, {}]), 1)


# ---------------------------------------------------------------- V2


def test_V2_followers_on_closed_region_rejected():
    """V2 (R-004, R-302): a controlled or unstable region must hold 0 followers."""
    for st in ("S", "W", "E", "unstable"):
        _rejected(_state(struggles=1, region_state={"Moray": st}, regions={"Moray": {"S": 1}}), 2)


def test_V2_closed_region_empty_and_followers_elsewhere_accepted():
    """V2 boundary: closed region empty, followers on open regions, accepted."""
    s = _load(_state(struggles=1, region_state={"Moray": "S"}, regions={"Strathclyde": {"S": 1}}))
    assert _counts(s)[0] == [0, 0, 0]
    assert _counts(s)[1] == [1, 0, 0]


# ---------------------------------------------------------------- V3


def test_V3_two_unstable_accepted_three_nonterminal_rejected():
    """V3 (R-304): fewer than 3 unstable is fine; 3 unstable where the slot-`struggles` region is
    not one of them is rejected; 4 unstable rejected."""
    _load(_state(struggles=2, region_state={"Moray": "unstable", "Strathclyde": "unstable"}))
    _rejected(
        _state(
            struggles=4,
            region_state={
                "Moray": "unstable",
                "Strathclyde": "unstable",
                "Lancaster": "unstable",
                "Northumbria": "S",
            },
        ),
        3,
    )
    _rejected(
        _state(
            struggles=4,
            region_state={r: "unstable" for r in REGIONS[:4]},
        ),
        3,
    )


def test_V3_terminal_by_invasion_accepted():
    """V3 boundary: exactly 3 unstable, the slot-`struggles` region among them, struggles < 8, is
    a terminal-by-invasion position and loads (R-304)."""
    s = _load(
        _state(
            struggles=3,
            region_state={r: "unstable" for r in REGIONS[:3]},
            last_play=[None, None],
        )
    )
    assert s.is_terminal()
    assert s.legal_actions() == []


def test_V3_terminal_by_invasion_with_non_last_unstable_slot():
    """V3: the third unstable region may sit in an earlier slot only if it is slot `struggles`;
    3 unstable in slots 1,2,4 with struggles=4 is accepted, with struggles=3 it is rejected by V4
    (closed set must be slots 1..3)."""
    ok = _state(
        struggles=4,
        region_state={
            "Moray": "unstable",
            "Strathclyde": "S",
            "Lancaster": "unstable",
            "Northumbria": "unstable",
        },
    )
    assert _load(ok).is_terminal()
    bad = _state(
        struggles=3,
        region_state={
            "Moray": "unstable",
            "Strathclyde": "unstable",
            "Northumbria": "unstable",
        },
    )
    _rejected_any(bad)  # violates V3 and V4; the message may name either


# ---------------------------------------------------------------- V4


def test_V4_struggles_must_equal_closed_count():
    """V4 (R-300, R-303): struggles must equal the number of closed regions."""
    _rejected(_state(struggles=2, region_state={"Moray": "S"}), 4)
    _rejected(_state(struggles=0, region_state={"Moray": "S"}), 4)
    _rejected(_state(struggles=1), 4)


def test_V4_closed_regions_must_be_slots_1_to_k():
    """V4: the closed regions are exactly those in slots 1..struggles."""
    _rejected(_state(struggles=1, region_state={"Strathclyde": "W"}), 4)
    _rejected(_state(struggles=2, region_state={"Moray": "S", "Lancaster": "E"}), 4)


def test_V4_follows_slots_order_not_region_order():
    """V4 boundary: with a permuted slot order the closed region is the one in slot 1."""
    slots = ["Devon", *REGIONS[:7]]
    s = _load(_state(struggles=1, slots=slots, region_state={"Devon": "W"}))
    assert s.struggles_resolved == 1
    _rejected(_state(struggles=1, slots=slots, region_state={"Moray": "W"}), 4)


def test_V4_struggles_range():
    """SCENARIOS 1: struggles is 0..8; 9 and -1 are rejected."""
    _rejected_any(_state(struggles=9))
    _rejected_any(_state(struggles=-1))


def test_V4_eight_struggles_accepted():
    """V4 boundary: all eight regions closed (terminal, no invasion) loads."""
    st = ["S", "W", "E", "S", "W", "E", "S", "W"]
    s = _load(_state(struggles=8, region_state=dict(zip(REGIONS, st, strict=True))))
    assert s.is_terminal()


# ---------------------------------------------------------------- V5


def test_V5_region_state_values():
    """V5 (R-303, R-004): region_state values are S, W, E or unstable; anything else rejected."""
    for bad in ("X", "open", "", None, 1, "s"):
        _rejected_any(_state(struggles=1, region_state={"Moray": bad}))
    for ok in ("S", "W", "E", "unstable"):
        _load(_state(struggles=1, region_state={"Moray": ok}))


def test_V5_recent_win_is_derived_from_slots():
    """V5/SCENARIOS derived: recent_win = highest slot number <= struggles controlled by the
    faction, -1 if none."""
    s = _load(
        _state(
            struggles=3,
            region_state={"Moray": "S", "Strathclyde": "unstable", "Lancaster": "S"},
        )
    )
    assert [int(x) for x in s.recent_win] == [3, -1, -1]
    s = _load(_state(struggles=2, region_state={"Moray": "E", "Strathclyde": "W"}))
    assert [int(x) for x in s.recent_win] == [-1, 2, 1]


# ---------------------------------------------------------------- V6


def test_V6_disc_requires_negotiate_spent():
    """V6 (R-006, R-213): a non-null negotiation entry needs `negotiate` out of that hand."""
    base = {"last_play": [1, None], "last_card": {"type": "negotiate"}}
    _rejected(_state(hands=[_hand(), _hand()], negotiation=["Lancaster", None]), 6)
    s = _load(_state(hands=[_hand("negotiate"), _hand()], negotiation=["Lancaster", None], **base))
    assert s.negotiation_discs[0] == REGIONS.index("Lancaster")
    assert s.negotiation_discs[1] is None


def test_V6_null_entry_after_negotiate_without_effect_accepted():
    """V6/R-213: null entry is allowed with negotiate out of hand (a Negotiate with no effect)."""
    s = _load(
        _state(
            hands=[_hand("negotiate"), _hand()],
            negotiation=[None, None],
            last_play=[1, None],
            last_card={"type": "negotiate"},
        )
    )
    assert all(d is None for d in s.negotiation_discs)


def test_V6_disc_on_two_players_same_region_rejected():
    """V6: no two players name the same region."""
    d = _state(
        hands=[_hand("negotiate"), _hand("negotiate")],
        negotiation=["Lancaster", "Lancaster"],
        last_play=[1, 2],
        last_card={"type": "negotiate"},
    )
    _rejected(d, 6)
    d["negotiation"] = ["Lancaster", "Devon"]
    s = _load(d)
    assert list(s.negotiation_discs) == [2, 7]


def test_V6_unknown_region_rejected():
    """V6: a negotiation entry must name a region."""
    _rejected_any(
        _state(
            hands=[_hand("negotiate"), _hand()],
            negotiation=["Atlantis", None],
            last_play=[1, None],
            last_card={"type": "negotiate"},
        )
    )


def test_V6_disc_may_be_on_face_down_card():
    """V6: a card carrying a disc may be face up or face down."""
    s = _load(
        _state(
            struggles=1,
            region_state={"Moray": "S"},
            hands=[_hand("negotiate"), _hand()],
            negotiation=["Moray", None],
            last_play=[1, None],
            last_card={"type": "negotiate"},
        )
    )
    assert s.negotiation_discs[0] == 0


def test_V6_negotiation_length_must_match_players():
    """SCENARIOS 1: negotiation has one entry per player."""
    _rejected_any(_state(2, negotiation=[None]))
    _rejected_any(_state(3, negotiation=[None, None]))


# ---------------------------------------------------------------- V7


def _played(p0_remove, p1_remove=()):
    return [_hand(*p0_remove), _hand(*p1_remove)]


def test_V7_valid_play_record_accepted():
    """V7 (R-102, R-401): total = sum(8 - hand size); last_play distinct, in 1..total, >= each
    player's play count, max = total and owned by the last player."""
    s = _load(
        _state(
            hands=_played(
                ["manoeuvre", "outmanoeuvre", "negotiate"], ["welsh_support", "assemble"]
            ),
            last_play=[5, 4],
            last_card={"type": "negotiate"},
        )
    )
    assert s.plays_total == 5
    s = _load(
        _state(
            hands=_played(["manoeuvre"]),
            last_play=[1, None],
            last_card={"type": "manoeuvre"},
        )
    )
    assert s.plays_total == 1


def test_V7_largest_last_play_must_equal_total():
    """V7: the largest last_play must equal the card-play total."""
    _rejected(
        _state(
            hands=_played(["manoeuvre"]),
            last_play=[2, None],
            last_card={"type": "manoeuvre"},
        ),
        7,
    )
    _rejected(
        _state(
            hands=_played(["manoeuvre", "negotiate"]),
            last_play=[1, None],
            last_card={"type": "manoeuvre"},
        ),
        7,
    )


def test_V7_last_play_distinct():
    """V7: last_play values are distinct."""
    _rejected(
        _state(
            hands=_played(["manoeuvre"], ["negotiate"]),
            last_play=[2, 2],
            last_card={"type": "manoeuvre"},
        ),
        7,
    )


def test_V7_last_play_at_least_cards_played():
    """V7: a player's last_play is at least the number of cards they played."""
    _rejected(
        _state(
            hands=_played(
                ["manoeuvre", "outmanoeuvre", "negotiate"], ["welsh_support", "assemble"]
            ),
            last_play=[5, 1],
            last_card={"type": "negotiate"},
        ),
        7,
    )


def test_V7_null_exactly_for_player_who_played_nothing():
    """V7: last_play is null exactly for a player with no cards played."""
    _rejected(
        _state(
            hands=_played(["manoeuvre"], ["negotiate"]),
            last_play=[2, None],
            last_card={"type": "manoeuvre"},
        ),
        7,
    )
    _rejected(
        _state(
            hands=_played(["manoeuvre"]),
            last_play=[1, 1],
            last_card={"type": "manoeuvre"},
        ),
        7,
    )


def test_V7_hand_empty_matches_empty_hand():
    """V7: hand_empty non-null exactly for an empty hand, equal to that player's last_play."""
    empty_hand = []
    kw = dict(
        hands=[empty_hand, _hand()],
        last_play=[8, None],
        last_card={"type": "assemble"},
    )
    _rejected(_state(**kw, hand_empty=[None, None]), 7)
    _rejected(_state(**kw, hand_empty=[7, None]), 7)
    s = _load(_state(**kw, hand_empty=[8, None]))
    assert s.plays_total == 8
    _rejected(
        _state(
            hands=_played(["manoeuvre"]),
            last_play=[1, None],
            last_card={"type": "manoeuvre"},
            hand_empty=[1, None],
        ),
        7,
    )


def test_V7_last_play_length_must_match_players():
    """SCENARIOS 1: last_play has one entry per player."""
    _rejected_any(_state(3, last_play=[None, None]))


# ---------------------------------------------------------------- V8


def test_V8_hand_must_be_sub_multiset():
    """V8 (R-008): too many copies, unknown cards and wrong length are rejected; both Assembles
    and the full hand are accepted; the empty hand is accepted (with a consistent record)."""
    _load(_state(hands=[_hand(), _hand()]))
    _rejected(_state(hands=[_hand() + ["assemble"], _hand()]), 8)
    _rejected(_state(hands=[_hand() + ["negotiate"], _hand()]), 8)
    _rejected_any(_state(hands=[_hand() + ["cunning"], _hand()]))
    _rejected_any(_state(hands=[_hand()]))
    _rejected_any(_state(3, hands=[_hand(), _hand()]))


def test_V8_hand_of_one_assemble_is_ok():
    """V8 boundary: a single copy of assemble is within the starting multiset."""
    s = _load(
        _state(
            hands=[["assemble"], _hand()],
            last_play=[7, None],
            last_card={"type": "manoeuvre"},
        )
    )
    assert s.plays_total == 7
    assert s.legal_actions() == [0, 4]


# ---------------------------------------------------------------- V9


@pytest.mark.parametrize("players,bad", [(2, 2), (3, 3)])
def test_V9_pass_count_bound(players, bad):
    """V9 (R-103): pass_count < players; players-1 accepted, players rejected."""
    s = _load(_state(players, pass_count=players - 1))
    assert s.pass_count == players - 1
    _rejected(_state(players, pass_count=bad), 9)
    _rejected_any(_state(players, pass_count=-1))


# ---------------------------------------------------------------- V10


def test_V10_last_card_null_iff_total_zero():
    """V10 (R-102, R-216): last_card is null iff no card has been played."""
    _rejected(_state(last_card={"type": "assemble"}), 10)
    _rejected(
        _state(hands=_played(["manoeuvre"]), last_play=[1, None], last_card=None),
        10,
    )
    _load(_state(last_card=None))


def test_V10_last_card_not_in_last_players_hand():
    """V10: type is a card the most recent player no longer holds."""
    d = _state(hands=_played(["manoeuvre"]), last_play=[1, None])
    d["last_card"] = {"type": "outmanoeuvre"}
    _rejected(d, 10)
    d["last_card"] = {"type": "manoeuvre"}
    _load(d)


def test_V10_other_players_hand_is_irrelevant():
    """V10 boundary: the card may still be in the other player's hand."""
    _load(
        _state(
            hands=_played(["manoeuvre"], ()),
            last_play=[1, None],
            last_card={"type": "manoeuvre"},
        )
    )


def test_V10_assemble_needs_at_most_one_copy_left():
    """V10: for assemble, at most one copy may be left in the player's hand."""
    d = _state(hands=_played(["manoeuvre"]), last_play=[1, None], last_card={"type": "assemble"})
    _rejected(d, 10)
    d = _state(hands=_played(["assemble"]), last_play=[1, None], last_card={"type": "assemble"})
    _load(d)
    d = _state(
        hands=_played(["assemble", "assemble"]),
        last_play=[2, None],
        last_card={"type": "assemble"},
    )
    _load(d)


def test_V10_reference_board_only_for_manoeuvre_types():
    """V10/SCENARIOS 1: reference_board is allowed only when last_card.type is manoeuvre or
    outmanoeuvre."""
    rb = {"regions": {"Moray": {"S": 1}}, "region_state": {}}
    base = dict(courts=[{}, {}])
    for ok in ("manoeuvre", "outmanoeuvre"):
        _load(
            _state(
                hands=_played([ok]),
                last_play=[1, None],
                last_card={"type": ok, "reference_board": rb},
                **base,
            )
        )
    _rejected(
        _state(
            hands=_played(["negotiate"]),
            last_play=[1, None],
            last_card={"type": "negotiate", "reference_board": rb},
        ),
        10,
    )


def test_V10_reference_board_obeys_V1_and_V2():
    """V10: reference_board is itself checked against V1 (pool) and V2 (closed
    regions empty); the error names V1/V2."""
    kw = dict(hands=_played(["outmanoeuvre"]), last_play=[1, None])
    over = {"regions": {"Moray": {"S": 17}}, "region_state": {}}
    _rejected(_state(**kw, last_card={"type": "outmanoeuvre", "reference_board": over}), 1)
    closed = {"regions": {"Moray": {"S": 1}}, "region_state": {"Moray": "W"}}
    _rejected(_state(**kw, last_card={"type": "outmanoeuvre", "reference_board": closed}), 2)
    fine = {"regions": {"Moray": {"S": 16}}, "region_state": {}}
    _load(_state(**kw, last_card={"type": "outmanoeuvre", "reference_board": fine}))


def test_V10_omitted_reference_board_is_void_and_accepted():
    """SCENARIOS 1 (D22): omitting reference_board for a manoeuvre card is allowed (B* void)."""
    _load(
        _state(
            hands=_played(["manoeuvre"]),
            last_play=[1, None],
            last_card={"type": "manoeuvre"},
        )
    )


# ---------------------------------------------------------------- V11


def test_V11_valid_setup_accepted_2p_and_3p():
    """V11 (R-011..R-014): the boundary setup (4 per region, home minimums met, courts of 2)
    loads for 2 and 3 players."""
    for n in (2, 3):
        _load(_setup(n))


def test_V11_region_must_hold_exactly_four():
    """V11 (R-013): 3 or 5 followers on a region is rejected."""
    d = _setup()
    d["regions"]["Devon"] = {"S": 1, "W": 1, "E": 1}
    _rejected(d, 11)
    d = _setup()
    d["regions"]["Devon"] = {"S": 2, "W": 2, "E": 1}
    _rejected(d, 11)
    d = _setup()
    del d["regions"]["Devon"]
    _rejected(d, 11)


def test_V11_home_minimums():
    """V11 (R-011): Moray >= 2 Scottish, Gwynedd >= 2 Welsh, Essex >= 2 English."""
    d = _setup()
    d["regions"]["Moray"] = {"S": 1, "W": 2, "E": 1}
    _rejected(d, 11)
    d = _setup()
    d["regions"]["Gwynedd"] = {"S": 2, "W": 1, "E": 1}
    _rejected(d, 11)
    d = _setup()
    d["regions"]["Essex"] = {"S": 2, "W": 1, "E": 1}
    _rejected(d, 11)
    d = _setup()
    d["regions"]["Moray"] = {"S": 4}
    d["regions"]["Gwynedd"] = {"W": 4}
    d["regions"]["Essex"] = {"E": 4}
    _load(d)


def test_V11_courts_exactly_two():
    """V11 (R-012): each court has exactly 2 followers."""
    for bad in ({"S": 1}, {"S": 2, "W": 1}, {}):
        d = _setup()
        d["courts"][0] = bad
        _rejected(d, 11)


def test_V11_pool_still_applies():
    """V11: all V1 constraints hold for a setup scenario too: 17 Scottish in 2p."""
    d = _setup()
    d["regions"] = {
        "Moray": {"S": 4},
        "Strathclyde": {"S": 4},
        "Lancaster": {"S": 4},
        "Northumbria": {"S": 4},
        "Gwynedd": {"W": 4},
        "Warwick": {"W": 4},
        "Essex": {"E": 4},
        "Devon": {"E": 4},
    }
    d["courts"] = [{"S": 2}, {"W": 2}]
    _rejected(d, 1)


def test_V11_not_applied_to_state_kind():
    """V11 applies to `setup` only: the same 3-follower region is fine in a `state` scenario."""
    s = _load(_state(regions={"Devon": {"S": 1, "W": 1, "E": 1}}))
    assert _counts(s)[7] == [1, 1, 1]


# ---------------------------------------------------------------- round trip


@pytest.mark.parametrize("path", SCEN_FILES, ids=lambda p: p.name)
def test_pickle_round_trip_preserves_state_and_observation(path):
    """Round trip: load, pickle, unpickle gives equal board, legal actions, observation tensor and
    string for every player, and the clone keeps playing identically."""
    s = load_scenario(str(path))
    t = pickle.loads(pickle.dumps(s))
    assert _counts(t) == _counts(s)
    assert [int(x) for x in t.supply] == [int(x) for x in s.supply]
    assert t.is_terminal() == s.is_terminal()
    assert t.legal_actions() == s.legal_actions()
    for p in range(s.get_game().num_players()):
        assert list(t.observation_tensor(p)) == list(s.observation_tensor(p))
        assert t.observation_string(p) == s.observation_string(p)
    if not s.is_terminal():
        a = s.legal_actions()[0]
        c = t.clone()
        s.apply_action(a)
        c.apply_action(a)
        assert c.legal_actions() == s.legal_actions()
        assert _counts(c) == _counts(s)


@pytest.mark.parametrize("players", [2, 3])
def test_pickle_round_trip_setup_scenario(players):
    """Round trip for generated setup scenarios in 2p and 3p."""
    s = _load(_setup(players))
    t = pickle.loads(pickle.dumps(s))
    for p in range(players):
        assert list(t.observation_tensor(p)) == list(s.observation_tensor(p))
        assert t.observation_string(p) == s.observation_string(p)
    assert _counts(t) == _counts(s)
