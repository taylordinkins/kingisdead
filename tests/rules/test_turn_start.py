"""Acceptance tests for turn start, pass and pass-count: R-101..R-106 (Phase 2 unit 4).

Assumed identifiers (same as test_setup.py, read through public attributes of the state):
  s.pass_count, s.struggles_resolved, s.plays_total, s.hands[p] (card id -> copies),
  s.region_counts, s.courts, s.supply.
Action ids per docs/ACTIONS.md section 2: PASS = 0, PLAY(c) = c for c in 1..7.
A card play is completed by always taking the first legal sub-step action until the turn passes
to another seat (``_play``); this avoids depending on the sub-step masks of units 5-7.
Struggle outcomes (units 8/9) are not asserted here, only the trigger.
"""

import random

import pyspiel
import pytest

PASS = 0
START_HAND = {1: 1, 2: 1, 3: 1, 4: 2, 5: 1, 6: 1, 7: 1}
ALL_CARDS = [1, 2, 3, 4, 4, 5, 6, 7]


def _new(players=2, seed=1):
    import kingisdead.game  # noqa: F401

    game = pyspiel.load_game(f"python_king_is_dead(players={players})")
    s = game.new_initial_state()
    rng = random.Random(seed)
    while s.is_chance_node():
        outs = s.chance_outcomes()
        s.apply_action(rng.choices([o for o, _ in outs], weights=[p for _, p in outs])[0])
    return s


def _play(s, card):
    """Play ``card`` and take first legal sub-steps until another seat is to move."""
    p = s.current_player()
    assert card in s.legal_actions()
    s.apply_action(card)
    guard = 0
    while not s.is_terminal() and s.current_player() == p:
        s.apply_action(s.legal_actions()[0])
        guard += 1
        assert guard < 8
    assert not s.is_terminal()


def _hand(s, p):
    return {c: n for c, n in dict(s.hands[p]).items() if n}


def _board(s):
    return (
        [list(map(int, r)) for r in s.region_counts],
        [list(map(int, r)) for r in s.courts],
        list(map(int, s.supply)),
    )


def _empty_hands(s):
    """Alternate plays until every hand is empty (n players, 8 cards each); no passes."""
    n = s.num_players()
    for card in ALL_CARDS:
        for _ in range(n):
            _play(s, card)


# ---------------------------------------------------------------- R-101


@pytest.mark.parametrize("players", [2, 3])
def test_R101_full_hand_offers_pass_and_all_seven_cards(players):
    """R-101: a player holding every card may pass or play any of the 7 card types."""
    s = _new(players)
    assert s.legal_actions() == [0, 1, 2, 3, 4, 5, 6, 7]


def test_R101_only_pass_and_cards_are_legal_at_turn_start():
    """R-101 (negative): no sub-step ids (8..39) are legal at the start of a turn."""
    s = _new()
    assert all(a <= 7 for a in s.legal_actions())
    assert not set(range(8, 40)) & set(s.legal_actions())


def test_R101_single_copy_card_leaves_legal_set_once_played():
    """R-101 / R-102: after playing Scottish Support (1 copy), PLAY(1) is no longer legal."""
    s = _new()
    _play(s, 1)  # seat 0
    s.apply_action(PASS)  # seat 1
    assert s.current_player() == 0
    assert s.legal_actions() == [0, 2, 3, 4, 5, 6, 7]


def test_R101_assemble_has_two_copies():
    """R-101 / R-008: Assemble stays legal after one play and disappears after the second."""
    s = _new()
    _play(s, 4)
    s.apply_action(PASS)
    assert 4 in s.legal_actions()
    _play(s, 4)
    s.apply_action(PASS)
    assert 4 not in s.legal_actions()
    assert s.legal_actions() == [0, 1, 2, 3, 5, 6, 7]


def test_R101_hands_are_per_player():
    """R-101: seat 0 playing a card does not remove it from seat 1's legal actions."""
    s = _new()
    _play(s, 7)
    assert s.current_player() == 1
    assert s.legal_actions() == [0, 1, 2, 3, 4, 5, 6, 7]


def test_R101_card_with_no_possible_effect_is_still_legal():
    """R-101: cards stay legal regardless of whether earlier plays exhausted their effects;
    after 1, 2, 3, 5, 6 are spent only Assemble and Outmanoeuvre remain, plus PASS."""
    s = _new()
    for card in (1, 2, 3, 5, 6):
        _play(s, card)
        s.apply_action(PASS)
    assert s.legal_actions() == [0, 4, 7]


def test_R101_playing_card_not_in_hand_is_rejected():
    """R-101 (negative): applying PLAY of a card no longer in hand raises."""
    s = _new()
    _play(s, 1)
    s.apply_action(PASS)
    with pytest.raises(Exception):  # noqa: B017
        s.apply_action(1)


def test_R101_legal_actions_sorted_and_unique():
    """R-101: the mask is sorted without duplicates (Assemble's two copies are one action)."""
    s = _new()
    la = s.legal_actions()
    assert la == sorted(set(la))


# ---------------------------------------------------------------- R-102


def test_R102_hand_decrements_after_completed_play():
    """R-102 example: after Manoeuvre and its summon, the player's hand has 7 cards."""
    s = _new()
    assert sum(_hand(s, 0).values()) == 8
    _play(s, 6)
    assert sum(_hand(s, 0).values()) == 7
    assert _hand(s, 0) == {**START_HAND, 6: 0} or _hand(s, 0) == {
        c: n for c, n in START_HAND.items() if c != 6
    }
    assert _hand(s, 1) == START_HAND


def test_R102_plays_total_counts_each_play():
    """R-102: plays_total increments once per card play, not per sub-step, and not on pass."""
    s = _new()
    _play(s, 4)
    assert s.plays_total == 1
    s.apply_action(PASS)
    assert s.plays_total == 1
    _play(s, 1)
    assert s.plays_total == 2


def test_R102_player_plays_at_most_eight_cards():
    """R-102: after eight plays a hand is empty and no card ids remain legal."""
    s = _new()
    for card in ALL_CARDS:
        _play(s, card)
        s.apply_action(PASS)
    assert _hand(s, 0) == {}
    assert s.legal_actions() == [PASS]


def test_R102_pass_keeps_hand():
    """R-102 (negative): passing does not remove a card from the hand."""
    s = _new()
    s.apply_action(PASS)
    assert _hand(s, 0) == START_HAND


# ---------------------------------------------------------------- R-103


def test_R103_pass_increments_pass_count_and_advances_seat_3p():
    """R-103 example: 3 players: count 0, player 1 passes -> count 1, player 2 to act."""
    s = _new(3)
    _play(s, 4)  # seat 0
    assert s.pass_count == 0
    assert s.current_player() == 1
    s.apply_action(PASS)
    assert s.pass_count == 1
    assert s.current_player() == 2


def test_R103_pass_changes_no_board_state():
    """R-103: a pass leaves regions, courts and supply untouched."""
    s = _new(3)
    before = _board(s)
    s.apply_action(PASS)
    assert _board(s) == before
    assert s.plays_total == 0


def test_R103_pass_is_legal_with_full_hand_and_may_repeat():
    """R-103 / R-101: PASS is always legal; a passing player may pass again next turn."""
    s = _new(3)
    s.apply_action(PASS)
    _play(s, 1)  # seat 1 acts -> count resets
    s.apply_action(PASS)  # seat 2
    s.apply_action(PASS)  # seat 0 again
    assert 0 in s.legal_actions()
    assert s.pass_count == 2


def test_R103_two_player_first_pass():
    """R-103: 2 players: seat 0 passes -> count 1, seat 1 to act, no struggle yet."""
    s = _new(2)
    s.apply_action(PASS)
    assert s.pass_count == 1
    assert s.current_player() == 1
    assert s.struggles_resolved == 0


# ---------------------------------------------------------------- R-104


def test_R104_play_resets_pass_count():
    """R-104 example: passes by players 0 and 1, then player 2 plays Assemble -> count 0."""
    s = _new(3)
    s.apply_action(PASS)
    s.apply_action(PASS)
    assert s.pass_count == 2
    _play(s, 4)
    assert s.pass_count == 0
    assert s.struggles_resolved == 0
    assert s.current_player() == 0


@pytest.mark.parametrize("card", [1, 2, 3, 4, 5, 6, 7])
def test_R104_every_card_type_resets_count(card):
    """R-104: whichever card is played (even one with no effect), the count resets to 0."""
    s = _new(2)
    s.apply_action(PASS)
    assert s.pass_count == 1
    _play(s, card)
    assert s.pass_count == 0


def test_R104_count_restarts_from_zero_after_reset():
    """R-104: after a reset, n-1 further passes are needed again before a struggle (2 players)."""
    s = _new(2)
    s.apply_action(PASS)  # seat 0
    _play(s, 4)  # seat 1 resets
    assert s.pass_count == 0
    s.apply_action(PASS)  # seat 0
    assert s.pass_count == 1
    assert s.struggles_resolved == 0


def test_R104_pass_after_play_does_not_accumulate_across_play():
    """R-104 (negative): pass, play, pass, play never reaches the struggle threshold (3 players)."""
    s = _new(3)
    for card in (1, 2, 3):
        s.apply_action(PASS)
        _play(s, card)
        assert s.pass_count == 0
    assert s.struggles_resolved == 0


# ---------------------------------------------------------------- R-105


@pytest.mark.parametrize("players", [2, 3])
def test_R105_no_struggle_before_n_passes(players):
    """R-105: the first n-1 consecutive passes only raise the count; no struggle yet."""
    s = _new(players)
    for i in range(players - 1):
        s.apply_action(PASS)
        assert s.pass_count == i + 1
        assert s.struggles_resolved == 0
    assert not s.is_terminal()


@pytest.mark.pending("R-105")
@pytest.mark.parametrize("players", [2, 3])
def test_R105_nth_pass_starts_struggle_and_resets_count(players):
    """R-105 (struggle is unit 8/9, count reset is the observable here): the nth consecutive pass
    resolves a struggle and resets the count to 0."""
    s = _new(players)
    for _ in range(players):
        s.apply_action(PASS)
    assert s.struggles_resolved == 1
    assert s.pass_count == 0


@pytest.mark.pending("R-105")
def test_R105_example_player_after_last_passer_acts_3p():
    """R-105 example (struggle part: unit 8/9): 3 players: seat 0 plays a card; 1, 2, 0 pass ->
    struggle. The player after the last passer (seat 1) acts next. (The spec text of the example
    says 'player 1 plays; 2, 0, 1 pass; player 2 acts', same shape shifted by one seat.)"""
    s = _new(3)
    s.apply_action(PASS)  # seat 0
    _play(s, 4)  # seat 1
    assert s.current_player() == 2
    for _ in range(3):  # seats 2, 0, 1
        s.apply_action(PASS)
    assert s.struggles_resolved == 1
    assert s.pass_count == 0
    if not s.is_terminal():
        assert s.current_player() == 2


def test_R105_struggle_needs_consecutive_passes():
    """R-105 (negative): pass, pass, play, pass, pass with 3 players does not trigger a struggle."""
    s = _new(3)
    s.apply_action(PASS)
    s.apply_action(PASS)
    _play(s, 4)
    s.apply_action(PASS)
    s.apply_action(PASS)
    assert s.pass_count == 2
    assert s.struggles_resolved == 0


@pytest.mark.pending("R-105")
def test_R105_struggle_does_not_change_hands():
    """R-105 (struggle is unit 8/9): a triggered struggle leaves every hand unchanged."""
    s = _new(2)
    for _ in range(2):
        s.apply_action(PASS)
    assert _hand(s, 0) == START_HAND
    assert _hand(s, 1) == START_HAND


# ---------------------------------------------------------------- R-106


@pytest.mark.parametrize("players", [2, 3])
def test_R106_empty_hand_only_pass_legal(players):
    """R-106 / R-101: a player with no cards has PASS as the only legal action."""
    s = _new(players)
    _empty_hands(s)
    assert s.current_player() == 0
    assert _hand(s, 0) == {}
    assert s.legal_actions() == [PASS]


@pytest.mark.pending("R-106")
def test_R106_only_the_empty_player_is_restricted():
    """R-106: with seat 0 empty and seat 1 still holding cards, seat 1 keeps all its options."""
    s = _new(2)
    for card in ALL_CARDS:
        _play(s, card)  # seat 0
        s.apply_action(PASS)  # seat 1 never plays
    assert s.legal_actions() == [PASS]  # seat 0 empty
    s.apply_action(PASS)
    assert s.current_player() == 1 or s.struggles_resolved >= 1
    if s.current_player() == 1:
        assert s.legal_actions() == [0, 1, 2, 3, 4, 5, 6, 7]


def test_R106_empty_hand_pass_increments_count():
    """R-106 / R-103: a forced pass by an empty-handed player counts toward R-105 (3 players:
    seats 0 and 1 are empty in turn... here all hands empty, one pass gives count 1)."""
    s = _new(3)
    _empty_hands(s)
    s.apply_action(PASS)
    assert s.pass_count == 1
    assert s.struggles_resolved == 0


@pytest.mark.pending("R-106")
def test_R106_all_empty_two_players_pass_pass_is_struggle():
    """R-106 example (struggle: unit 8/9): 2 players, empty hands: pass, pass -> struggle."""
    s = _new(2)
    _empty_hands(s)
    s.apply_action(PASS)
    s.apply_action(PASS)
    assert s.struggles_resolved == 1
    assert s.pass_count == 0


@pytest.mark.pending("R-106")
def test_R106_all_empty_game_terminates_within_eight_struggles():
    """R-106 (needs units 8/9 and R-304): with every hand empty, repeated passing ends the game
    after at most 8 struggles."""
    s = _new(2)
    _empty_hands(s)
    passes = 0
    while not s.is_terminal():
        assert s.legal_actions() == [PASS]
        s.apply_action(PASS)
        passes += 1
        assert passes <= 8 * 2
    assert s.struggles_resolved <= 8
