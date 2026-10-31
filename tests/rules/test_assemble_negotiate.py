"""Acceptance tests for Assemble and Negotiate: R-212, R-213 (Phase 2 unit 6), R-200..R-202.

Assumed identifiers (same as test_support_summon.py / test_setup.py):
  s.region_counts[r][f], s.courts[p][f], s.supply[f], s.hands[p] (card -> copies),
  s.slot_regions[i] (region index in slot i+1), s.negotiation_discs[p] (region index or None),
  s.pass_count, s.plays_total; legal_actions(), current_player(), apply_action(), clone();
  ``kingisdead.scenario.load_scenario(dict)``.
The phase is inferred from legal_actions(): ids 8..15 = REGION step, ids >= 16 = SUMMON.
PLAY(c) = c (4 Assemble, 5 Negotiate), REGION(r) = 8 + r, FOLLOWER(r, f) = 16 + 3r + f.
Negotiation discs are placed by ``_pos`` through the scenario ``negotiation`` field (SCENARIOS.md);
the card of a region is identified by region index (ACTIONS.md section 2), and canonical order
(r2 > r1) is by REGION INDEX, not slot (see report: ambiguity note on "higher region index").
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
CLOSE_CYCLE = ["S", "W", "E"]
ASSEMBLE, NEGOTIATE = 4, 5


def region(r):
    return 8 + r


def follower(r, f):
    return 16 + 3 * r + f


def _pos(
    slots=None, nclosed=0, regions=None, supply=None, players=2, discs=None, last_negotiate=False
):
    """State with ``slots`` (region index per slot, default identity), the first ``nclosed``
    slots closed (states cycling S, W, E), player 0 to act. ``discs``: {player: region index}
    spent discs (that player's hand loses negotiate). Default regions: one follower of each
    faction on every open region. Supply defaults to 3 each, remainder in the last court."""
    from kingisdead.scenario import load_scenario

    slots = list(slots) if slots is not None else list(range(8))
    closed = {slots[i]: CLOSE_CYCLE[i % 3] for i in range(nclosed)}
    discs = discs or {}
    if regions is None:
        regions = {r: {0: 1, 1: 1, 2: 1} for r in range(8) if r not in closed}
    supply = {0: 3, 1: 3, 2: 3, **(supply or {})}
    court = {}
    for f in range(3):
        used = sum(c.get(f, 0) for c in regions.values())
        rest = POOL[players] - used - supply[f]
        assert rest >= 0
        if rest:
            court[FN[f]] = rest
    hands = []
    for p in range(players):
        h = list(FULL_HAND)
        if p in discs:
            h.remove("negotiate")
        hands.append(h)
    data = {
        "format": 1,
        "kind": "state",
        "players": players,
        "slots": [REGIONS[r] for r in slots],
        "regions": {REGIONS[r]: {FN[f]: n for f, n in c.items() if n} for r, c in regions.items()},
        "courts": [{} for _ in range(players - 1)] + [court],
        "to_play": 0,
        "struggles": nclosed,
        "region_state": {REGIONS[r]: v for r, v in closed.items()},
        "hands": hands,
    }
    if discs:
        data["negotiation"] = [REGIONS[discs[p]] if p in discs else None for p in range(players)]
        # V7/V10: someone has played negotiate; attribute the last play to the lowest disc owner
        owner = min(discs)
        data["last_play"] = [1 if p == owner else None for p in range(players)]
        data["last_card"] = {"type": "negotiate"}
        # V7 total must equal sum of cards played
        assert sum(8 - len(h) for h in hands) == len(discs)
        if len(discs) > 1:
            data["last_play"] = [None] * players
            for i, p in enumerate(sorted(discs)):
                data["last_play"][p] = i + 1
            data["last_card"] = {"type": "negotiate"}
    return load_scenario(copy.deepcopy(data))


def _counts(s):
    return [list(map(int, row)) for row in s.region_counts]


def _courts(s):
    return [list(map(int, row)) for row in s.courts]


def _supply(s):
    return list(map(int, s.supply))


def _conserved(s, players=2):
    for f in range(3):
        total = (
            sum(row[f] for row in _counts(s)) + sum(row[f] for row in _courts(s)) + _supply(s)[f]
        )
        assert total == POOL[players], f"faction {f}: {total}"


def _hand(s, p):
    return {c: n for c, n in dict(s.hands[p]).items() if n}


def _open(slots=None, nclosed=0):
    slots = slots if slots is not None else list(range(8))
    return sorted(slots[nclosed:])


def _is_summon(legal):
    return bool(legal) and all(a >= 16 for a in legal)


# ---------------------------------------------------------------- R-212 Assemble


def test_R212_first_prompt_offers_every_open_region():
    """R-212: after PLAY(4) the first (Scottish) placement offers every open REGION(r)."""
    s = _pos()
    s.apply_action(ASSEMBLE)
    assert s.legal_actions() == [region(r) for r in range(8)]
    assert s.current_player() == 0


def test_R212_places_s_then_w_then_e_one_each_then_summon():
    """R-212: one Scottish, then one Welsh, then one English follower from the supply, each into
    the region chosen at that step; then the summon (R-201) follows."""
    s = _pos(regions={r: {0: 1} for r in range(8)})
    before = _counts(s)
    sup = _supply(s)
    s.apply_action(ASSEMBLE)
    s.apply_action(region(1))  # Scottish
    c = _counts(s)
    assert c[1][0] == before[1][0] + 1 and c[1][1] == before[1][1] and c[1][2] == before[1][2]
    assert s.legal_actions() == [region(r) for r in range(8)]
    s.apply_action(region(4))  # Welsh
    c = _counts(s)
    assert c[4][1] == before[4][1] + 1 and c[4][2] == before[4][2]
    s.apply_action(region(6))  # English
    c = _counts(s)
    assert c[6][2] == before[6][2] + 1
    assert _supply(s) == [x - 1 for x in sup]
    assert _is_summon(s.legal_actions())
    assert s.current_player() == 0
    _conserved(s)


def test_R212_all_three_may_go_to_same_region():
    """R-212: the regions may be equal; the same region is offered at every step."""
    s = _pos(regions={0: {0: 1}})
    s.apply_action(ASSEMBLE)
    for _ in range(3):
        assert region(2) in s.legal_actions()
        s.apply_action(region(2))
    assert _counts(s)[2] == [1, 1, 1]
    _conserved(s)


def test_R212_closed_regions_never_offered():
    """R-212 / R-200: with Moray (S), Strathclyde (W) and Lancaster (E) closed, only the other open
    regions are offered at each of the three steps."""
    s = _pos(nclosed=3)
    s.apply_action(ASSEMBLE)
    for _ in range(3):
        assert s.legal_actions() == [region(r) for r in range(3, 8)]
        s.apply_action(region(7))
    _conserved(s)


def test_R212_closed_regions_respect_slot_order_not_index():
    """R-212 / R-200: closed regions are those in slots 1..k; with slots [5,2,...] regions 5 and 2
    are closed and not offered even though their indices are mid-range."""
    slots = [5, 2, 0, 1, 3, 4, 6, 7]
    s = _pos(slots=slots, nclosed=2)
    s.apply_action(ASSEMBLE)
    assert s.legal_actions() == [region(r) for r in (0, 1, 3, 4, 6, 7)]


@pytest.mark.parametrize("empty", [0, 1, 2])
def test_R212_empty_supply_faction_skipped(empty):
    """R-212: a faction with no supply followers gets no step; the other two are still placed in
    S, W, E order. Two REGION prompts, then SUMMON; the empty faction's count never changes."""
    s = _pos(supply={empty: 0})
    before = _counts(s)
    s.apply_action(ASSEMBLE)
    assert s.legal_actions() == [region(r) for r in range(8)]
    s.apply_action(region(0))
    assert s.legal_actions() == [region(r) for r in range(8)]
    s.apply_action(region(1))
    assert _is_summon(s.legal_actions())
    c = _counts(s)
    others = [f for f in range(3) if f != empty]
    assert c[0][others[0]] == before[0][others[0]] + 1  # first placed faction goes first
    assert c[1][others[1]] == before[1][others[1]] + 1
    assert sum(r[empty] for r in c) == sum(r[empty] for r in before)
    assert _supply(s)[empty] == 0
    _conserved(s)


def test_R212_only_one_faction_available_single_prompt():
    """R-212: with only English in the supply, exactly one placement step, then SUMMON."""
    s = _pos(supply={0: 0, 1: 0, 2: 2})
    s.apply_action(ASSEMBLE)
    assert s.legal_actions() == [region(r) for r in range(8)]
    s.apply_action(region(3))
    assert _is_summon(s.legal_actions())
    assert _counts(s)[3][2] == 2
    _conserved(s)


def test_R212_empty_supply_everywhere_no_effect_goes_to_summon():
    """R-212 / R-202: if every faction's supply is empty Assemble has no sub-steps; the card is
    played and play goes straight to SUMMON. Board counts unchanged."""
    s = _pos(supply={0: 0, 1: 0, 2: 0})
    before = _counts(s)
    s.apply_action(ASSEMBLE)
    assert _is_summon(s.legal_actions())
    assert _counts(s) == before
    assert _hand(s, 0)[ASSEMBLE] == 1
    _conserved(s)


def test_R212_no_effect_and_empty_board_skips_summon():
    """R-212 / R-202 / R-201: supply empty and no followers on the board: no effect, summon
    skipped, turn passes to player 1 at TURN_START (PASS legal)."""
    s = _pos(regions={}, supply={0: 0, 1: 0, 2: 0})
    s.apply_action(ASSEMBLE)
    assert s.current_player() == 1
    assert 0 in s.legal_actions()


def test_R212_summon_sees_placed_followers():
    """R-212 / R-201: the summon after Assemble can take a follower just placed (empty board,
    full supply): SUMMON lists exactly the three placed (region, faction) pairs."""
    s = _pos(regions={}, supply={0: 1, 1: 1, 2: 1})
    s.apply_action(ASSEMBLE)
    s.apply_action(region(0))
    s.apply_action(region(2))
    s.apply_action(region(5))
    assert s.legal_actions() == sorted([follower(0, 0), follower(2, 1), follower(5, 2)])
    s.apply_action(follower(2, 1))
    assert _courts(s)[0][1] == 1
    _conserved(s)
    assert s.current_player() == 1


def test_R212_invalid_region_rejected():
    """R-212 / R-200: a closed region is not among the legal actions at the placement step."""
    s = _pos(nclosed=1)
    s.apply_action(ASSEMBLE)
    assert region(0) not in s.legal_actions()


def test_R212_three_players_acting_player_keeps_move():
    """R-212: in a 3-player game the acting player makes all three placements and the summon
    before the turn passes to seat 1."""
    s = _pos(players=3)
    s.apply_action(ASSEMBLE)
    for _ in range(3):
        assert s.current_player() == 0
        s.apply_action(region(1))
    assert s.current_player() == 0 and _is_summon(s.legal_actions())
    s.apply_action(s.legal_actions()[0])
    assert s.current_player() == 1
    _conserved(s, 3)


# ---------------------------------------------------------------- R-213 Negotiate


def test_R213_all_eligible_first_mask_excludes_highest_index():
    """R-213 / ACTIONS NEG_FIRST: with all 8 cards eligible, NEG_FIRST offers every card that has
    a partner of higher region index, i.e. regions 0..6 (not 7)."""
    s = _pos()
    s.apply_action(NEGOTIATE)
    assert s.legal_actions() == [region(r) for r in range(7)]


def test_R213_second_mask_is_higher_than_first():
    """R-213 / ACTIONS NEG_SECOND: after choosing r1 the second offers eligible regions r2 > r1."""
    s = _pos()
    s.apply_action(NEGOTIATE)
    s.apply_action(region(3))
    assert s.legal_actions() == [region(r) for r in (4, 5, 6, 7)]


def test_R213_disc_mask_is_the_two_chosen_regions():
    """R-213 / ACTIONS NEG_DISC: the disc step offers exactly REGION(first) and REGION(second)."""
    s = _pos()
    s.apply_action(NEGOTIATE)
    s.apply_action(region(2))
    s.apply_action(region(5))
    assert s.legal_actions() == [region(2), region(5)]
    assert s.current_player() == 0


@pytest.mark.parametrize("disc_on", [3, 5])
def test_R213_swap_slots_and_place_disc(disc_on):
    """R-213 example: swapping slots 3 and 5 (regions 2 and 4) exchanges them in slot_regions and
    the player's disc lands on the chosen region; regions keep their followers."""
    s = _pos()
    s.apply_action(NEGOTIATE)
    s.apply_action(region(2))
    s.apply_action(region(4))
    counts = _counts(s)
    s.apply_action(region(2 if disc_on == 3 else 4))
    assert list(s.slot_regions) == [0, 1, 4, 3, 2, 5, 6, 7]
    assert s.negotiation_discs[0] == (2 if disc_on == 3 else 4)
    assert s.negotiation_discs[1] is None
    assert _counts(s) == counts
    assert _is_summon(s.legal_actions())
    assert s.current_player() == 0
    _conserved(s)


def test_R213_disc_on_second_card_not_first():
    """R-213: the disc follows the region card chosen (the second pick), not the slot position."""
    s = _pos()
    s.apply_action(NEGOTIATE)
    s.apply_action(region(0))
    s.apply_action(region(7))
    s.apply_action(region(7))
    assert list(s.slot_regions) == [7, 1, 2, 3, 4, 5, 6, 0]
    assert s.negotiation_discs[0] == 7


def test_R213_negotiate_does_not_move_followers_or_states():
    """R-213 / R-200: negotiating changes only slots and the disc: counts, supply and courts are
    identical before and after (apart from the summon, which is not taken here)."""
    s = _pos()
    sup, crt = _supply(s), _courts(s)
    cnt = _counts(s)
    for a in (NEGOTIATE, region(1), region(6), region(6)):
        s.apply_action(a)
    assert (_counts(s), _supply(s), _courts(s)) == (cnt, sup, crt)


def test_R213_face_down_cards_not_eligible():
    """R-213: cards in slots 1..struggles are face down. With 3 closed (regions 0,1,2) only 3..7 are
    eligible: NEG_FIRST = 3..6, NEG_SECOND after 3 = 4..7."""
    s = _pos(nclosed=3)
    s.apply_action(NEGOTIATE)
    assert s.legal_actions() == [region(r) for r in (3, 4, 5, 6)]
    s.apply_action(region(3))
    assert s.legal_actions() == [region(r) for r in (4, 5, 6, 7)]


def test_R213_face_down_follows_slots_not_indices():
    """R-213: with slots [6,1,...] and 2 closed, regions 6 and 1 are face down; eligible = the
    others (0,2,3,4,5,7)."""
    slots = [6, 1, 0, 2, 3, 4, 5, 7]
    s = _pos(slots=slots, nclosed=2)
    s.apply_action(NEGOTIATE)
    assert s.legal_actions() == [region(r) for r in (0, 2, 3, 4, 5)]
    s.apply_action(region(5))
    assert s.legal_actions() == [region(7)]


def test_R213_swap_after_closures_updates_only_face_up_slots():
    """R-213: with 2 closed slots, swapping regions 3 and 7 leaves slots 1-2 untouched."""
    s = _pos(nclosed=2)
    for a in (NEGOTIATE, region(3), region(7), region(3)):
        s.apply_action(a)
    assert list(s.slot_regions) == [0, 1, 2, 7, 4, 5, 6, 3]
    assert s.negotiation_discs[0] == 3


def test_R213_card_with_disc_not_eligible():
    """R-213: a card carrying another player's disc is not eligible. Player 1's disc on region 4:
    NEG_FIRST = 0..6 minus 4 (4 absent), and 4 is not a partner either."""
    s = _pos(discs={1: 4})
    s.apply_action(NEGOTIATE)
    assert s.legal_actions() == [region(r) for r in (0, 1, 2, 3, 5, 6)]
    s.apply_action(region(3))
    assert s.legal_actions() == [region(r) for r in (5, 6, 7)]


def test_R213_disc_on_face_down_card_has_no_effect_on_eligibility():
    """R-213 / V6: a disc on a face-down card is irrelevant; the face-up cards are all eligible."""
    s = _pos(nclosed=2, discs={1: 0})
    s.apply_action(NEGOTIATE)
    assert s.legal_actions() == [region(r) for r in (2, 3, 4, 5, 6)]


def test_R213_partner_requirement_filters_first_mask():
    """R-213 / ACTIONS NEG_FIRST: an eligible card with no eligible partner of higher index is not
    offered. Eligible {1,3,6} (others discs/closed): firsts = {1,3}; 6 has no higher partner."""
    s = _pos(nclosed=1, discs={1: 2})  # Moray closed; Lancaster has disc
    # eligible: 1,3,4,5,6,7 -> restrict by a second disc via another seat in a 3-player game
    s = _pos(nclosed=1, discs={1: 4, 2: 5}, players=3)
    s.apply_action(NEGOTIATE)
    assert s.legal_actions() == [region(r) for r in (1, 2, 3, 6)]
    s.apply_action(region(6))
    # NEG_SECOND after 6 would be {7}
    assert s.legal_actions() == [region(7)]


def test_R213_exactly_two_eligible_swap_forced():
    """R-213: with exactly two eligible cards (struggles 6) the only first pick is the lower one
    and the only second pick is the higher one."""
    s = _pos(nclosed=6)
    s.apply_action(NEGOTIATE)
    assert s.legal_actions() == [region(6)]
    s.apply_action(region(6))
    assert s.legal_actions() == [region(7)]
    s.apply_action(region(7))
    assert s.legal_actions() == [region(6), region(7)]


def test_R213_one_eligible_no_effect_goes_to_summon():
    """R-213 / R-202: only one face-up card (struggles 7): no effect, no sub-steps, disc unused,
    play goes to SUMMON."""
    s = _pos(nclosed=7)
    s.apply_action(NEGOTIATE)
    assert _is_summon(s.legal_actions())
    assert s.negotiation_discs[0] is None
    assert list(s.slot_regions) == list(range(8))
    assert _hand(s, 0).get(NEGOTIATE, 0) == 0
    _conserved(s)


def test_R213_discs_leave_fewer_than_two_eligible_no_effect():
    """R-213: three closed + discs from seats 1 and 2 on two of the open cards leave 3 eligible in a
    3-player game: effect applies; with one more closed it is only 2... here 5 closed + disc on
    a face-up one leaves 1 eligible, so no effect and disc stays unused."""
    s = _pos(nclosed=6, discs={1: 6})
    s.apply_action(NEGOTIATE)
    assert _is_summon(s.legal_actions())
    assert s.negotiation_discs[0] is None


def test_R213_no_effect_when_no_followers_skips_summon():
    """R-213 / R-202 / R-201: no effect and no followers on regions: turn passes straight on."""
    s = _pos(nclosed=7, regions={})
    s.apply_action(NEGOTIATE)
    assert s.current_player() == 1
    assert 0 in s.legal_actions()


def test_R213_canonical_order_by_region_index_not_slot():
    """R-213 / ACTIONS section 5: r2 > r1 compares region indices even if slots are permuted.
    Slots [7,6,...]: slot 1 = region 7 (face down if closed; here none closed): first mask
    excludes region 7 (no higher index) regardless of its slot."""
    slots = [7, 6, 5, 4, 3, 2, 1, 0]
    s = _pos(slots=slots)
    s.apply_action(NEGOTIATE)
    assert s.legal_actions() == [region(r) for r in range(7)]
    s.apply_action(region(0))
    assert s.legal_actions() == [region(r) for r in range(1, 8)]
    s.apply_action(region(7))
    s.apply_action(region(0))
    assert list(s.slot_regions) == [0, 6, 5, 4, 3, 2, 1, 7]


def test_R213_each_pair_has_unique_sequence():
    """R-213 / ACTIONS section 5: count of (first, second) action pairs equals C(8,2) = 28 with
    all cards eligible (each unordered swap exactly one sequence)."""
    s = _pos()
    s.apply_action(NEGOTIATE)
    pairs = 0
    for a in s.legal_actions():
        t = s.clone()
        t.apply_action(a)
        pairs += len(t.legal_actions())
    assert pairs == 28


def test_R213_disc_is_spent_per_player_three_players():
    """R-213 / R-006: in a 3-player game seat 0's disc goes on its own slot; others' discs on
    the board are unchanged and those cards remain ineligible."""
    s = _pos(players=3, discs={1: 3})
    for a in (NEGOTIATE, region(0), region(1), region(1)):
        s.apply_action(a)
    assert s.negotiation_discs[0] == 1
    assert s.negotiation_discs[1] == 3
    assert s.negotiation_discs[2] is None
    _conserved(s, 3)


def test_R213_card_swapped_with_disc_stays_ineligible_later():
    """R-213 / R-006: after Negotiate, a later Negotiate by the next player cannot pick the card
    holding seat 0's disc (spent discs never return)."""
    s = _pos()
    for a in (NEGOTIATE, region(0), region(1), region(0)):
        s.apply_action(a)
    s.apply_action(s.legal_actions()[0])  # summon
    assert s.current_player() == 1
    s.apply_action(NEGOTIATE)
    assert region(0) not in s.legal_actions()
    s.apply_action(region(1))
    assert region(0) not in s.legal_actions()


def test_R213_summon_follows_and_follower_conserved():
    """R-213 / R-201: after the disc step the summon lists the followers on the board, and
    taking one moves it to the court, keeping totals."""
    s = _pos()
    for a in (NEGOTIATE, region(0), region(1), region(1)):
        s.apply_action(a)
    legal = s.legal_actions()
    assert legal == sorted(follower(r, f) for r in range(8) for f in range(3))
    s.apply_action(follower(1, 2))
    assert _courts(s)[0][2] == 1
    _conserved(s)
    assert s.current_player() == 1


def test_R213_hand_and_pass_count_after_negotiate():
    """R-102/R-104 with R-213: Negotiate leaves the hand without it and resets the pass count."""
    s = _pos()
    for a in (NEGOTIATE, region(0), region(1), region(0)):
        s.apply_action(a)
    assert _hand(s, 0).get(NEGOTIATE, 0) == 0
    assert s.pass_count == 0
