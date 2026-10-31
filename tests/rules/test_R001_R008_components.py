"""Acceptance tests for R-001..R-006 and R-008: constants and board.

Assumed identifiers in ``kingisdead.constants`` (spec does not fix them):
  NUM_REGIONS: int; REGION_NAMES: sequence of str indexed by region;
  ADJACENCY: sequence indexed by region of iterables of neighbour indices;
  NUM_FACTIONS: int; FACTION_NAMES: sequence of str indexed by faction;
  HOME_REGION: sequence indexed by faction -> region index;
  FOLLOWERS_PER_FACTION: mapping player_count -> int;
  CONTROL_DISCS_PER_FACTION, INSTABILITY_DISCS: int;
  REGION_OPEN / REGION_CONTROLLED / REGION_UNSTABLE: distinct region-state values;
  CARD_NAMES: mapping card id (1..7, docs/ACTIONS.md) -> str;
  STARTING_HAND: mapping card id -> copy count.
"""

SPEC_NAMES = [
    "Moray",
    "Strathclyde",
    "Lancaster",
    "Northumbria",
    "Gwynedd",
    "Warwick",
    "Essex",
    "Devon",
]

SPEC_ADJ = {
    "Moray": {"Strathclyde"},
    "Strathclyde": {"Moray", "Lancaster", "Northumbria"},
    "Lancaster": {"Strathclyde", "Northumbria", "Gwynedd", "Warwick"},
    "Northumbria": {"Strathclyde", "Lancaster", "Warwick", "Essex"},
    "Gwynedd": {"Lancaster", "Warwick", "Devon"},
    "Warwick": {"Lancaster", "Northumbria", "Gwynedd", "Essex", "Devon"},
    "Essex": {"Northumbria", "Warwick", "Devon"},
    "Devon": {"Gwynedd", "Warwick", "Essex"},
}


def _c():
    from kingisdead import constants

    return constants


def test_R001_region_indices_and_names():
    """R-001: eight regions with fixed indices 0..7 in the stated order."""
    c = _c()
    assert c.NUM_REGIONS == 8
    assert list(c.REGION_NAMES) == SPEC_NAMES
    assert c.REGION_NAMES[4] == "Gwynedd"


def test_R001_france_is_not_a_region():
    """R-001: France is not indexed; no region named France, no index 8."""
    c = _c()
    assert "France" not in list(c.REGION_NAMES)
    assert len(c.REGION_NAMES) == 8
    assert len(c.ADJACENCY) == 8


def test_R002_adjacency_exact():
    """R-002: adjacency is exactly the listed table."""
    c = _c()
    for i, name in enumerate(SPEC_NAMES):
        got = {SPEC_NAMES[j] for j in c.ADJACENCY[i]}
        assert got == SPEC_ADJ[name], name


def test_R002_adjacency_symmetric_irreflexive():
    """R-002: symmetric, no region adjacent to itself."""
    c = _c()
    for i in range(8):
        assert i not in set(c.ADJACENCY[i])
        for j in c.ADJACENCY[i]:
            assert i in set(c.ADJACENCY[j])


def test_R002_examples_and_non_adjacent():
    """R-002 example: Moray borders only Strathclyde; Warwick five; Moray/Devon not bordering."""
    c = _c()
    assert set(c.ADJACENCY[0]) == {1}
    assert len(set(c.ADJACENCY[5])) == 5
    assert 7 not in set(c.ADJACENCY[0])
    assert 6 not in set(c.ADJACENCY[4])  # Gwynedd-Essex not adjacent


def test_R003_factions_and_homes():
    """R-003: factions 0 Scottish, 1 Welsh, 2 English; homes Moray, Gwynedd, Essex."""
    c = _c()
    assert c.NUM_FACTIONS == 3
    assert list(c.FACTION_NAMES) == ["Scottish", "Welsh", "English"]
    assert list(c.HOME_REGION) == [0, 4, 6]
    assert c.REGION_NAMES[c.HOME_REGION[2]] == "Essex"


def test_R004_region_states_distinct():
    """R-004: three distinct region states: open, controlled, unstable."""
    c = _c()
    states = {c.REGION_OPEN, c.REGION_CONTROLLED, c.REGION_UNSTABLE}
    assert len(states) == 3


def test_R005_follower_pool_counts():
    """R-005: 18 per faction in 3p (54 total), 16 in 2p (48 total)."""
    c = _c()
    assert c.FOLLOWERS_PER_FACTION[3] == 18
    assert c.FOLLOWERS_PER_FACTION[2] == 16
    assert 3 * c.FOLLOWERS_PER_FACTION[3] == 54
    assert 3 * c.FOLLOWERS_PER_FACTION[2] == 48


def test_R005_no_other_player_count_pool():
    """R-005/R-007: no pool size defined for 5 players (base game)."""
    c = _c()
    assert 5 not in c.FOLLOWERS_PER_FACTION


def test_R006_disc_counts():
    """R-006: 8 control discs per faction, 3 instability discs."""
    c = _c()
    assert c.CONTROL_DISCS_PER_FACTION == 8
    assert c.INSTABILITY_DISCS == 3


def test_R008_starting_hand_contents():
    """R-008: 2 Assemble and 1 of each other card; 8 cards total."""
    c = _c()
    names = {cid: c.CARD_NAMES[cid] for cid in range(1, 8)}
    assert names == {
        1: "Scottish Support",
        2: "Welsh Support",
        3: "English Support",
        4: "Assemble",
        5: "Negotiate",
        6: "Manoeuvre",
        7: "Outmanoeuvre",
    }
    hand = dict(c.STARTING_HAND)
    assert sum(hand.values()) == 8
    assert hand[4] == 2
    assert all(hand[k] == 1 for k in (1, 2, 3, 5, 6, 7))


def test_R008_no_cunning_cards():
    """R-008: cunning action cards are not used; hand holds only the seven kinds."""
    c = _c()
    assert set(dict(c.STARTING_HAND)) == set(range(1, 8))
