"""Acceptance tests for action/chance encoding: docs/ACTIONS.md sections 1-3 and R-007.

Assumed identifiers in ``kingisdead.actions`` (the spec does not fix them):
  NUM_DISTINCT_ACTIONS = 40, MAX_CHANCE_OUTCOMES = 8
  PASS = 0
  play_action(card) -> id; region_action(r) -> id; follower_action(r, f) -> id
  decode_action(id) -> object with attributes ``kind`` in {"PASS","PLAY","REGION","FOLLOWER"}
      and ``card`` / ``region`` / ``faction`` (None when not applicable)
  action_label(id) -> str
  decode_chance_outcome(outcome, kind) with kind in {"region", "faction"} -> region/faction index
  encode_chance_outcome(value, kind) -> outcome id
  Out-of-range IDs raise ValueError.
"""

import pytest


def _a():
    from kingisdead import actions

    return actions


def _fields(d):
    return (d.kind, d.card, d.region, d.faction)


def test_R007_action_count_and_chance_count():
    """ACTIONS 2/3: num_distinct_actions = 40, max_chance_outcomes = 8."""
    a = _a()
    assert a.NUM_DISTINCT_ACTIONS == 40
    assert a.MAX_CHANCE_OUTCOMES == 8


def test_R007_pass_is_zero():
    """ACTIONS 2: PASS = 0."""
    a = _a()
    assert a.PASS == 0
    d = a.decode_action(0)
    assert d.kind == "PASS"
    assert (d.card, d.region, d.faction) == (None, None, None)


@pytest.mark.parametrize("c", range(1, 8))
def test_R007_play_ids_equal_card(c):
    """ACTIONS 2: PLAY(c) = c for c in 1..7."""
    a = _a()
    assert a.play_action(c) == c
    assert _fields(a.decode_action(c)) == ("PLAY", c, None, None)


@pytest.mark.parametrize("r", range(8))
def test_R007_region_ids(r):
    """ACTIONS 2: REGION(r) = 8 + r."""
    a = _a()
    assert a.region_action(r) == 8 + r
    assert _fields(a.decode_action(8 + r)) == ("REGION", None, r, None)


@pytest.mark.parametrize("r", range(8))
@pytest.mark.parametrize("f", range(3))
def test_R007_follower_ids(r, f):
    """ACTIONS 2: FOLLOWER(r, f) = 16 + 3r + f."""
    a = _a()
    assert a.follower_action(r, f) == 16 + 3 * r + f
    assert _fields(a.decode_action(16 + 3 * r + f)) == ("FOLLOWER", None, r, f)


def test_R007_follower_range_is_16_to_39():
    """ACTIONS 2: FOLLOWER IDs cover exactly 16..39."""
    a = _a()
    ids = {a.follower_action(r, f) for r in range(8) for f in range(3)}
    assert ids == set(range(16, 40))


def test_R007_roundtrip_all_40():
    """ACTIONS 2: encode(decode(id)) == id for all 40 IDs."""
    a = _a()
    enc = {
        "PASS": lambda d: a.PASS,
        "PLAY": lambda d: a.play_action(d.card),
        "REGION": lambda d: a.region_action(d.region),
        "FOLLOWER": lambda d: a.follower_action(d.region, d.faction),
    }
    for i in range(40):
        d = a.decode_action(i)
        assert enc[d.kind](d) == i


@pytest.mark.parametrize("bad", [-1, 40, 41, 100, -40])
def test_R007_decode_rejects_out_of_range(bad):
    """ACTIONS 2: IDs outside 0..39 are not actions (must NOT decode)."""
    a = _a()
    with pytest.raises(ValueError):
        a.decode_action(bad)
    with pytest.raises(ValueError):
        a.action_label(bad)


@pytest.mark.parametrize("c", [0, 8, -1])
def test_R007_play_rejects_bad_card(c):
    """ACTIONS 1: card c is in 1..7 only."""
    with pytest.raises(ValueError):
        _a().play_action(c)


@pytest.mark.parametrize("r", [-1, 8])
def test_R007_region_rejects_bad_region(r):
    """ACTIONS 1: region r is in 0..7 only."""
    a = _a()
    with pytest.raises(ValueError):
        a.region_action(r)
    with pytest.raises(ValueError):
        a.follower_action(r, 0)


@pytest.mark.parametrize("f", [-1, 3])
def test_R007_follower_rejects_bad_faction(f):
    """ACTIONS 1: faction f is in 0..2 only."""
    with pytest.raises(ValueError):
        _a().follower_action(0, f)


def test_R007_labels_nonempty_and_unique():
    """ACTIONS 2: every ID has a non-empty human-readable label, distinct per ID."""
    a = _a()
    labels = [a.action_label(i) for i in range(40)]
    assert all(isinstance(s, str) and s.strip() for s in labels)
    assert len(set(labels)) == 40


def test_R007_labels_mention_names():
    """ACTIONS 1: labels for REGION/FOLLOWER actions name the region (and faction)."""
    from kingisdead import constants as k

    a = _a()
    for r in range(8):
        assert k.REGION_NAMES[r].lower() in a.action_label(8 + r).lower()
        for f in range(3):
            lab = a.action_label(16 + 3 * r + f).lower()
            assert k.REGION_NAMES[r].lower() in lab
            assert k.FACTION_NAMES[f].lower() in lab


def test_R007_labels_for_cards_use_card_names():
    """ACTIONS 1: PLAY(c) label contains the card name (R-008 names)."""
    from kingisdead import constants as k

    a = _a()
    for c in range(1, 8):
        assert k.CARD_NAMES[c].lower() in a.action_label(c).lower()


def test_R007_constants_agree_with_action_index_ranges():
    """ACTIONS 1: index ranges match the constants (8 regions, 3 factions, 7 cards)."""
    from kingisdead import constants as k

    assert k.NUM_REGIONS == 8
    assert k.NUM_FACTIONS == 3
    assert len(k.CARD_NAMES) == 7
    assert 1 + 7 + k.NUM_REGIONS + k.NUM_REGIONS * k.NUM_FACTIONS == 40


@pytest.mark.parametrize("r", range(8))
def test_R007_chance_region_outcome_is_region_index(r):
    """ACTIONS 3 step 1: region-card outcome is the region index r."""
    a = _a()
    assert a.decode_chance_outcome(r, "region") == r
    assert a.encode_chance_outcome(r, "region") == r


@pytest.mark.parametrize("f", range(3))
def test_R007_chance_faction_outcome_is_faction_index(f):
    """ACTIONS 3 steps 2-3: court draw / region fill outcome is the faction index f."""
    a = _a()
    assert a.decode_chance_outcome(f, "faction") == f
    assert a.encode_chance_outcome(f, "faction") == f


@pytest.mark.parametrize("bad", [-1, 3, 8])
def test_R007_chance_faction_rejects_out_of_range(bad):
    """ACTIONS 3: a faction outcome must be in 0..2 (must NOT decode)."""
    with pytest.raises(ValueError):
        _a().decode_chance_outcome(bad, "faction")


@pytest.mark.parametrize("bad", [-1, 8, 9])
def test_R007_chance_region_rejects_out_of_range(bad):
    """ACTIONS 3: a region outcome must be in 0..7 (must NOT decode)."""
    with pytest.raises(ValueError):
        _a().decode_chance_outcome(bad, "region")
