"""Acceptance tests for game end and scoring: R-400..R-405 (Phase 2 unit 9), with the R-304 ordering
(invasion is checked before coronation).

Assumed identifiers (same style as test_power_struggle.py):
  s.is_terminal(), s.legal_actions(), s.returns() (list, one float per player),
  s.player_return(p), s.struggles_resolved, s.region_states[r], s.pass_count,
  s.last_play[p] and s.hand_empty[p] (card-play number, 1-based, R-401; "none" is accepted as
    None or any value <= 0, see ``_rec``), s.recent_win[f] (R-303), s.hands[p],
  ``kingisdead.scenario.load_scenario(dict)``;
  PASS = 0, PLAY(c) = c (1 Scottish Support, 2 Welsh Support, 3 English Support, 4 Assemble,
  5 Negotiate, 6 Manoeuvre, 7 Outmanoeuvre).
Return values convention (R-405): k winners among n: winner (n-k)/(k(n-1)), loser -1/(n-1).
Positions are scenarios (SCENARIOS.md). ``_scn`` takes the closed regions as a list of states in
slot order; slot i+1 holds region i (ascending index), so the region of the next struggle is
region ``len(states)``. Records are injected through ``last_play`` (hand_empty is derived: equal to
last_play for a player with an empty hand, V7).
"""

import copy
import json
import pathlib

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
SC = pathlib.Path(__file__).resolve().parent.parent / "scenarios"
PASS = 0
U = "unstable"


def pend(rule):
    return pytest.mark.pending(rule)


# ---------------------------------------------------------------- state building


def _scn(
    players,
    states,
    courts,
    *,
    sizes=None,
    last_play=None,
    board=None,
    to_play=0,
    pass_count=0,
):
    """``states``: closed-region states in slot order ('S','W','E','unstable'); ``courts``: list
    of {'S':n,...}; ``sizes``: hand size per player (default 8); ``last_play``: list of int/None;
    ``board``: {region index: count map} for open regions."""
    from kingisdead.scenario import load_scenario

    sizes = sizes or [8] * players
    data = {
        "format": 1,
        "kind": "state",
        "players": players,
        "slots": list(REGIONS),
        "regions": {REGIONS[r]: c for r, c in (board or {}).items()},
        "courts": copy.deepcopy(courts),
        "to_play": to_play,
        "pass_count": pass_count,
        "struggles": len(states),
        "region_state": {REGIONS[i]: st for i, st in enumerate(states)},
        "hands": [FULL_HAND[:n] for n in sizes],
    }
    if last_play is not None:
        data["last_play"] = list(last_play)
        data["hand_empty"] = [
            lp if n == 0 else None for lp, n in zip(last_play, sizes, strict=True)
        ]
        if any(lp is not None for lp in last_play):
            data["last_card"] = {"type": "outmanoeuvre"}
    return load_scenario(data)


def _rec(v):
    return None if v is None or v <= 0 else int(v)


def _exp(n, winners):
    k = len(winners)
    return [(n - k) / (k * (n - 1)) if p in winners else -1 / (n - 1) for p in range(n)]


def _check_result(s, n, winners):
    assert s.is_terminal()
    assert s.legal_actions() == []
    assert s.returns() == pytest.approx(_exp(n, winners))
    assert sum(s.returns()) == pytest.approx(0)
    for p in range(n):
        assert s.player_return(p) == pytest.approx(_exp(n, winners)[p])


def _unstable(s):
    from kingisdead import constants

    return sum(1 for st in s.region_states if st == constants.REGION_UNSTABLE)


def _drive(s, card):
    """Play ``card`` for the current player and finish its sub-steps and summon with the first
    legal action each time, until the turn passes to someone else."""
    me = s.current_player()
    assert card in s.legal_actions()
    s.apply_action(card)
    while not s.is_terminal() and s.current_player() == me:
        s.apply_action(s.legal_actions()[0])


# ================================================================ R-400 end triggers


@pytest.mark.parametrize("players", [2, 3])
def test_R400_third_unstable_region_ends_game_with_struggles_left(players):
    """R-400: the struggle that places the third instability disc ends the game although only the
    third struggle has been resolved; no actions are left, no fourth struggle is possible."""
    courts = [{"S": 1}, {"W": 1}, {"E": 1}][:players]
    s = _scn(players, [U, U], courts, pass_count=players - 1)
    assert not s.is_terminal()
    for _ in range(1):
        s.apply_action(PASS)  # contested Lancaster is empty: unstable
    assert s.struggles_resolved == 3
    assert _unstable(s) == 3
    assert s.is_terminal()
    assert s.legal_actions() == []
    assert s.struggles_resolved == 3


def test_R400_invasion_late_in_the_game():
    """R-400: invasion at the sixth struggle (two unstable earlier, third unstable now) ends it."""
    s = _scn(
        2,
        [U, "S", "W", U, "E"],
        [{"S": 1}, {"W": 1}],
        pass_count=1,
        board={5: {"S": 1, "W": 1}},
    )
    s.apply_action(PASS)
    assert s.struggles_resolved == 6
    assert _unstable(s) == 3
    assert s.is_terminal() and s.legal_actions() == []


def test_R400_coronation_after_eighth_struggle_with_two_unstable():
    """R-400: with only two unstable regions, the eighth struggle ends the game (coronation)."""
    s = _scn(
        2,
        ["S", U, "W", "E", U, "S", "W"],
        [{"S": 2}, {"W": 1}],
        pass_count=1,
        board={7: {"E": 3, "S": 1}},
    )
    assert not s.is_terminal()
    s.apply_action(PASS)
    assert s.struggles_resolved == 8
    assert _unstable(s) == 2
    assert s.is_terminal() and s.legal_actions() == []


def test_R400_game_not_over_before_the_final_struggle():
    """R-400 (negative): after the seventh struggle with two unstable regions the game is still
    running: PASS and card plays are legal, and returns are zero."""
    s = _scn(
        2,
        ["S", U, "W", "E", U, "S"],
        [{"S": 2}, {"W": 1}],
        pass_count=1,
        board={6: {"E": 1}, 7: {"S": 1}},
    )
    s.apply_action(PASS)
    assert s.struggles_resolved == 7
    assert not s.is_terminal()
    assert PASS in s.legal_actions() and 1 in s.legal_actions()
    assert s.returns() == [0, 0]


def test_R400_two_unstable_never_ends_the_game_early():
    """R-400 (negative): two instability discs and a third controlled struggle: no end."""
    s = _scn(2, [U, U], [{"S": 1}, {"W": 1}], pass_count=1, board={2: {"S": 2}})
    s.apply_action(PASS)
    assert s.struggles_resolved == 3 and _unstable(s) == 2
    assert not s.is_terminal()


def test_R400_terminal_state_stays_terminal_with_no_actions():
    """R-400: an ended game has no legal actions and its returns do not change when queried."""
    s = _scn(2, [U, U], [{"S": 1}, {"W": 1}], pass_count=1)
    s.apply_action(PASS)
    first = list(s.returns())
    assert s.legal_actions() == []
    assert list(s.returns()) == first
    assert s.is_terminal()


# ================================================================ R-405 returns convention


@pytest.mark.parametrize("players", [2, 3])
def test_R405_returns_are_zero_at_start_and_mid_game(players):
    """R-405: returns are zero for every player at every non-terminal state: a fresh position,
    after a card play, after a pass, and after a non-final struggle."""
    courts = [{"S": 1}, {"W": 1}, {"E": 1}][:players]
    s = _scn(players, [], courts, board={0: {"S": 2}, 1: {"W": 1}, 2: {"E": 1}, 3: {"S": 1}})
    assert s.returns() == [0] * players
    _drive(s, 6)  # Manoeuvre
    assert s.returns() == [0] * players
    for _ in range(players):
        s.apply_action(PASS)
    assert s.struggles_resolved == 1 and not s.is_terminal()
    assert s.returns() == [0] * players
    assert all(s.player_return(p) == 0 for p in range(players))


def test_R405_returns_zero_one_pass_before_the_end():
    """R-405: returns are still zero when the next pass would end the game."""
    s = _scn(2, [U, U], [{"S": 2}, {"W": 2}], pass_count=1)
    assert not s.is_terminal()
    assert s.returns() == [0, 0]


def test_R405_formula_values():
    """R-405 examples: n=3 one winner +1 / -1/2 / -1/2; n=3 two winners +1/4 +1/4 -1/2; n=2
    sole winner +1 / -1; n=2 shared 0 / 0; n=3 shared by all 0."""
    assert _exp(3, [1]) == pytest.approx([-0.5, 1, -0.5])
    assert _exp(3, [0, 2]) == pytest.approx([0.25, -0.5, 0.25])
    assert _exp(2, [0]) == pytest.approx([1, -1])
    assert _exp(2, [0, 1]) == pytest.approx([0, 0])
    assert _exp(3, [0, 1, 2]) == pytest.approx([0, 0, 0])


# ================================================================ R-402 invasion winner

THREE_U = [U, U, U]


def _inv(courts, last_play=None, sizes=None):
    players = len(courts)
    return _scn(players, THREE_U, courts, last_play=last_play, sizes=sizes)


def test_R402_most_complete_sets_wins_even_if_other_played_last():
    """R-402: sets = min over factions of court counts; most sets wins; last-play only breaks
    ties. P0 has 2 sets, P1 0 sets but played last."""
    s = _inv(
        [{"S": 3, "W": 2, "E": 2}, {"S": 5, "E": 1}],
        last_play=[1, 2],
        sizes=[7, 7],
    )
    _check_result(s, 2, [0])


def test_R402_sets_are_the_minimum_not_the_total():
    """R-402: P0 has many followers but no English (0 sets); P1 has one of each (1 set)."""
    s = _inv([{"S": 5, "W": 5}, {"S": 1, "W": 1, "E": 1}])
    _check_result(s, 2, [1])


def test_R402_example_tie_goes_to_latest_last_play():
    """R-402 example: P0 [S S W E], P1 [S W E E]: both 1 set; P1 played the later card -> P1."""
    s = _inv(
        [{"S": 2, "W": 1, "E": 1}, {"S": 1, "W": 1, "E": 2}],
        last_play=[3, 4],
        sizes=[6, 6],
    )
    _check_result(s, 2, [1])


def test_R402_tie_goes_to_latest_last_play_reversed():
    """R-402: same courts, P0 played the later card -> P0 wins (order, not seat)."""
    s = _inv(
        [{"S": 2, "W": 1, "E": 1}, {"S": 1, "W": 1, "E": 2}],
        last_play=[4, 3],
        sizes=[6, 6],
    )
    _check_result(s, 2, [0])


def test_R402_last_play_is_most_recent_card_not_number_of_cards():
    """R-402 / R-401: P0 played more cards (7) but P1's single card was the latest overall:
    P1 wins the tie on the highest last-play number."""
    s = _inv(
        [{"S": 1, "W": 1, "E": 1}, {"S": 1, "W": 1, "E": 1}],
        last_play=[6, 7],
        sizes=[2, 7],
    )
    _check_result(s, 2, [1])


def test_R402_player_who_never_played_loses_to_tied_player_who_did():
    """R-402: a player with no last-play loses to a tied player who played at all, in either
    seat order."""
    for lp, winner in (([None, 1], 1), ([1, None], 0)):
        sizes = [8, 7] if winner == 1 else [7, 8]
        s = _inv([{"S": 1, "W": 1, "E": 1}] * 2, last_play=lp, sizes=sizes)
        _check_result(s, 2, [winner])


def test_R402_nobody_played_tied_players_share_the_win():
    """R-402 / R-405: no tied player ever played: they share; 2 players -> 0, 0."""
    s = _inv([{"S": 2, "W": 2, "E": 2}, {"S": 2, "W": 2, "E": 2}])
    _check_result(s, 2, [0, 1])


def test_R402_three_players_two_tied_never_played_share_and_third_loses():
    """R-402 / R-405: P0 and P1 tie on 2 sets, nobody played: shared win, k=2 of n=3."""
    s = _inv(
        [{"S": 2, "W": 2, "E": 2}, {"S": 2, "W": 3, "E": 2}, {"S": 1, "W": 1, "E": 1}],
    )
    _check_result(s, 3, [0, 1])


def test_R402_tie_break_applies_only_among_tied_players():
    """R-402: P2 has fewer sets but played the latest card; the tie is P0 vs P1 only, and P0
    (the later of the two) wins."""
    s = _inv(
        [{"S": 2, "W": 2, "E": 2}, {"S": 2, "W": 2, "E": 2}, {"S": 1, "W": 1, "E": 1}],
        last_play=[5, 4, 6],
        sizes=[6, 6, 6],
    )
    _check_result(s, 3, [0])


def test_R402_three_way_tie_latest_player_wins():
    """R-402: all three players tie on sets; the most recent last-play (P1, 5) wins."""
    s = _inv(
        [{"S": 1, "W": 1, "E": 1}] * 3,
        last_play=[3, 5, 4],
        sizes=[6, 6, 7],
    )
    _check_result(s, 3, [1])


def test_R402_hand_emptied_order_is_not_used_in_invasion():
    """R-402 (negative): P0 emptied their hand (hand-empty 8) while P1 played last (9): the
    invasion tie goes to P1 by last-play; hand-empty is a coronation tie-break only."""
    s = _inv(
        [{"S": 1, "W": 1, "E": 1}, {"S": 1, "W": 1, "E": 1}],
        last_play=[8, 9],
        sizes=[0, 7],
    )
    _check_result(s, 2, [1])


def test_R402_invasion_at_early_struggle_uses_courts_not_regions():
    """R-402: regions controlled by factions do not matter; P0's court has 1 set, P1's 2 sets."""
    s = _scn(
        2,
        ["S", "S", "S", U, "S", U, U],
        [{"S": 6, "W": 1, "E": 1}, {"S": 2, "W": 2, "E": 2}],
    )
    # 7 struggles resolved, region 6 (slot 7) is unstable: terminal invasion.
    _check_result(s, 2, [1])


def test_R402_invasion_via_real_play_tie_broken_by_recorded_last_play():
    """R-402 / R-401: a card actually played is recorded: P1 plays Scottish Support (no supply,
    no effect, no followers on the board so no summon); P0 and P1 pass; the empty Lancaster is
    unstable (third) -> invasion; equal sets, only P1 ever played -> P1 wins."""
    court = {"S": 8, "W": 4, "E": 4}
    s = _scn(2, [U, U], [court, court], to_play=1)
    s.apply_action(1)
    assert _rec(s.last_play[1]) == 1 and _rec(s.last_play[0]) is None
    s.apply_action(PASS)
    s.apply_action(PASS)
    assert s.is_terminal()
    _check_result(s, 2, [1])


def test_R402_invasion_via_real_play_other_seat():
    """R-402 / R-401: as above with seat 0 playing: P0 wins the tie."""
    court = {"S": 8, "W": 4, "E": 4}
    s = _scn(2, [U, U], [court, court], to_play=0)
    s.apply_action(1)
    s.apply_action(PASS)
    s.apply_action(PASS)
    _check_result(s, 2, [0])


# ================================================================ R-401 records


def test_R401_none_before_any_play():
    """R-401: at the start nobody has a last-play or hand-empty number."""
    s = _scn(2, [], [{"S": 1}, {"W": 1}], board={0: {"S": 1}})
    assert [_rec(x) for x in s.last_play] == [None, None]
    assert [_rec(x) for x in s.hand_empty] == [None, None]


def test_R401_card_plays_are_numbered_across_players_from_one():
    """R-401: card plays are counted across the game from 1; passes and summons do not count.
    P1 plays (1), P0 passes, P1 passes... P0 then plays (2), P1 plays (3)."""
    board = {r: {"S": 1, "W": 1} for r in range(8)}
    s = _scn(2, [], [{"S": 1}, {"W": 1}], board=board, to_play=1)
    _drive(s, 2)  # P1 plays Welsh Support: play 1
    assert [_rec(x) for x in s.last_play] == [None, 1]
    _drive(s, 4)  # P0: play 2
    assert [_rec(x) for x in s.last_play] == [2, 1]
    s.apply_action(PASS)  # P1 passes: no number
    assert [_rec(x) for x in s.last_play] == [2, 1]
    s.apply_action(PASS)  # P0 passes -> struggle
    assert [_rec(x) for x in s.last_play] == [2, 1]
    assert s.struggles_resolved == 1
    _drive(s, 5)  # P1: play 3 (Negotiate is the seat-1 card now)
    assert [_rec(x) for x in s.last_play] == [2, 3]


def test_R401_last_play_keeps_only_the_most_recent_card_of_each_player():
    """R-401: a player's number is that of their most recent card: P0 plays cards 1 and 3, so
    last_play[0] = 3."""
    board = {r: {"S": 1, "W": 1} for r in range(8)}
    s = _scn(2, [], [{"S": 1}, {"W": 1}], board=board)
    _drive(s, 4)
    _drive(s, 4)
    _drive(s, 2)
    assert [_rec(x) for x in s.last_play] == [3, 2]


def test_R401_hand_empty_is_play_number_of_the_eighth_card():
    """R-401 example: the hand-empty time is the overall play number at which the hand became
    empty. Two players alternate all eight cards: P0 empties at play 15, P1 at play 16."""
    board = {r: {"S": 1, "W": 1} for r in range(8)}
    s = _scn(
        2,
        [],
        [{"S": 1}, {"W": 1}],
        board=board,
        pass_count=0,
    )
    cards = [1, 2, 3, 4, 4, 5, 6, 7]
    for i, c in enumerate(cards):
        _drive(s, c)
        assert [_rec(x) for x in s.last_play][0] == 2 * i + 1
        if i < 7:
            assert _rec(s.hand_empty[0]) is None
        _drive(s, c)
        assert [_rec(x) for x in s.last_play] == [2 * i + 1, 2 * i + 2]
        if i < 7:
            assert [_rec(x) for x in s.hand_empty] == [None, None]
    assert [_rec(x) for x in s.hand_empty] == [15, 16]
    assert [_rec(x) for x in s.last_play] == [15, 16]


def test_R401_hand_empty_only_for_the_player_whose_hand_emptied():
    """R-401: after P0's eighth card (play 15 of a scenario with P1 having one card left), only
    P0 has a hand-empty number; P1's stays none."""
    s = _scn(
        2,
        [],
        [{"S": 1}, {"W": 1}],
        sizes=[1, 1],
        last_play=[13, 14],
        board={r: {"S": 1, "W": 1} for r in range(8)},
    )
    assert [_rec(x) for x in s.hand_empty] == [None, None]
    _drive(s, 1)  # P0's last card is Scottish Support (FULL_HAND[:1])
    assert _rec(s.hand_empty[0]) == 15 and _rec(s.last_play[0]) == 15
    assert _rec(s.hand_empty[1]) is None
    _drive(s, 1)
    assert _rec(s.hand_empty[1]) == 16


def test_R401_recent_win_is_recorded_per_faction_at_struggle_number():
    """R-401 / R-303: recent-win per faction: Welsh controls at struggle 2 (slot 2)."""
    s = _scn(2, ["S"], [{"S": 1}, {"W": 1}], pass_count=1, board={1: {"W": 3}})
    s.apply_action(PASS)
    assert list(s.recent_win) == [1, 2, -1]


# ================================================================ R-403 / R-404 coronation


def _cor(states, courts, **kw):
    assert len(states) == 8
    return _scn(len(courts), states, courts, **kw)


def test_R403_scenario_file_example_matches_spec():
    """R-403 / R-404 / R-405: tests/scenarios/coronation_tiebreak.json: rank 1 S, rank 2 W; P0
    and P1 tie on 2 Scottish; P1 has more Welsh and wins (+1, -1/2, -1/2)."""
    from kingisdead.scenario import load_scenario

    data = json.loads((SC / "coronation_tiebreak.json").read_text())
    s = load_scenario(copy.deepcopy(data))
    assert list(s.recent_win) == [8, 7, 4]
    _check_result(s, 3, [1])
    assert s.returns() == pytest.approx(data["example"]["expect"]["returns"])


def _json_variant(sc_courts, flip_last=False):
    from kingisdead.scenario import load_scenario

    data = json.loads((SC / "coronation_tiebreak.json").read_text())
    data.pop("example")
    data["courts"] = sc_courts
    if flip_last:
        # Strathclyde (slot 8) S -> W and Moray (slot 2) W -> S: W (not S) won last; still 3 v 3.
        data["region_state"]["Strathclyde"] = "W"
        data["region_state"]["Moray"] = "S"
    return load_scenario(data)


def test_R403_json_rank1_is_faction_with_latest_win_among_equal_regions():
    """R-403: S and W control 3 regions each; S won last (struggle 8) so rank 1 = S: the S count
    decides first. P0 [S3 W2] beats P1 [S2 W3]."""
    courts = [{"S": 3, "W": 2}, {"S": 2, "W": 3}, {"E": 1}]
    s = _json_variant(courts)
    _check_result(s, 3, [0])


def test_R403_json_rank1_flips_when_welsh_won_last():
    """R-403: the same courts with W winning the last struggle make W rank 1: P1 [S2 W3] wins."""
    courts = [{"S": 3, "W": 2}, {"S": 2, "W": 3}, {"E": 1}]
    s = _json_variant(courts, flip_last=True)
    assert list(s.recent_win)[1] == 8
    _check_result(s, 3, [1])


def test_R404_json_step2_zero_welsh_cannot_beat_one():
    """R-404 step 2: with rank 2 = W, P0 [S2 W1] beats P1 [S2 W0] after the S tie."""
    courts = [{"S": 2, "W": 1}, {"S": 2}, {"S": 1, "E": 4}]
    s = _json_variant(courts)
    _check_result(s, 3, [0])


def test_R403_regions_controlled_rank_above_recent_win():
    """R-403: S 4 regions (oldest wins), W 3, E 1 (latest win, slot 8). Ranking is by regions
    first, so rank 2 = W (not E). P0 and P1 tie on S; P1 has W, P0 only E: P1 wins."""
    states = ["S", "S", "S", "S", "W", "W", "W", "E"]
    courts = [{"S": 2, "E": 3}, {"S": 2, "W": 1}, {"S": 1}]
    _check_result(_cor(states, courts), 3, [1])


def test_R403_tie_on_regions_broken_by_larger_recent_win_rank2_is_E():
    """R-403 example: S 4, W 2, E 2: W and E tie on regions; E won later (slot 8) so E is rank 2.
    P0 and P1 tie on S; P1 holds the English follower and wins."""
    states = ["S", "S", "S", "S", "W", "E", "W", "E"]
    courts = [{"S": 2, "W": 1}, {"S": 2, "E": 1}, {"S": 1, "W": 2, "E": 2}]
    _check_result(_cor(states, courts), 3, [1])


def test_R403_tie_on_regions_broken_by_larger_recent_win_rank2_is_W():
    """R-403: as above with W winning the last struggle: W is rank 2 and P0 wins."""
    states = ["S", "S", "S", "S", "E", "W", "E", "W"]
    courts = [{"S": 2, "W": 1}, {"S": 2, "E": 1}, {"S": 1, "W": 2, "E": 2}]
    _check_result(_cor(states, courts), 3, [0])


def test_R403_older_big_faction_still_outranks_newer_smaller_one_for_rank1():
    """R-403: W controls 5 regions (last win slot 5), S 3 (last win slot 8): rank 1 = W, so
    W counts decide: P1 [W3] beats P0 [S5 W1]."""
    states = ["W", "W", "W", "W", "W", "S", "S", "S"]
    courts = [{"S": 5, "W": 1}, {"W": 3}]
    _check_result(_cor(states, courts), 2, [1])


def test_R404_step1_unique_leader_in_rank1_faction_wins():
    """R-404 step 1: the most rank-1 followers wins outright, whatever else the others hold."""
    states = ["S", "S", "S", "S", "W", "W", "W", "E"]
    courts = [{"S": 3}, {"S": 1, "W": 5}, {"E": 5}]
    _check_result(_cor(states, courts), 3, [0])


def test_R404_example_rank2_decides_tie():
    """R-404 example: rank 1 S, rank 2 W; P0 [S S W], P1 [S S E], P2 [S]: P0 wins."""
    states = ["S", "S", "S", "S", "W", "W", "W", "E"]
    courts = [{"S": 2, "W": 1}, {"S": 2, "E": 1}, {"S": 1}]
    _check_result(_cor(states, courts), 3, [0])


def test_R404_step2_only_among_players_tied_after_step1():
    """R-404: P2 has the most rank-2 followers but fewer rank-1 followers: not in the tie.
    P0/P1 tie on S=2; W: P0 1, P1 2 -> P1; P2 (S1, W5) does not win."""
    states = ["S", "S", "S", "S", "W", "W", "W", "E"]
    courts = [{"S": 2, "W": 1}, {"S": 2, "W": 2}, {"S": 1, "W": 5}]
    _check_result(_cor(states, courts), 3, [1])


def test_R404_rank2_undefined_step_skipped_and_hand_empty_decides():
    """R-403 / R-404: S controls 6, W and E 0 (two unstable): rank 2 undefined, so the rank-2
    step is skipped. P0 and P1 tie on S=2; P1 has 5 Welsh but this must not count; hand-empty:
    P0 at 15 vs P1 at 16 -> P0 wins."""
    states = ["S", "S", U, "S", "S", U, "S", "S"]
    courts = [{"S": 2}, {"S": 2, "W": 5}]
    s = _cor(states, courts, sizes=[0, 0], last_play=[15, 16])
    _check_result(s, 2, [0])


def test_R404_rank2_undefined_hand_empty_other_order():
    """R-404 step 3: as above, P1 emptied first (14) while P0 emptied at 16 -> P1 wins."""
    states = ["S", "S", U, "S", "S", U, "S", "S"]
    courts = [{"S": 2, "W": 5}, {"S": 2}]
    s = _cor(states, courts, sizes=[0, 0], last_play=[16, 14])
    _check_result(s, 2, [1])


def test_R404_step3_player_who_emptied_hand_beats_one_who_did_not():
    """R-404 step 3: P0 never emptied (7 cards played, played last, last_play 15), P1 emptied
    at 14: P1 wins although P0 played last (last-play is not a coronation tie-break)."""
    states = ["S", "S", U, "S", "S", U, "S", "S"]
    s = _cor(states, [{"S": 2}, {"S": 2}], sizes=[1, 0], last_play=[15, 14])
    _check_result(s, 2, [1])


def test_R404_step3_other_seat_emptied():
    """R-404 step 3: mirror: only P0 emptied -> P0 wins."""
    states = ["S", "S", U, "S", "S", U, "S", "S"]
    s = _cor(states, [{"S": 2}, {"S": 2}], sizes=[0, 1], last_play=[14, 15])
    _check_result(s, 2, [0])


def test_R404_step3_nobody_emptied_share_win_two_players():
    """R-404 / R-405: no tied player emptied their hand: shared win, returns 0, 0 even though
    P1 played the latest card."""
    states = ["S", "S", U, "S", "S", U, "S", "S"]
    s = _cor(states, [{"S": 2}, {"S": 2}], sizes=[2, 1], last_play=[12, 13])
    _check_result(s, 2, [0, 1])


def test_R404_step3_nobody_played_share_win():
    """R-404 / R-405: nobody ever played: tie shared."""
    states = ["S", "S", U, "S", "S", U, "S", "S"]
    s = _cor(states, [{"S": 2}, {"S": 2}])
    _check_result(s, 2, [0, 1])


def test_R404_step3_applies_only_to_players_still_tied():
    """R-404: P2 emptied their hand first (play 9) but is not tied after step 1/2 (S=1); the
    winner is the earlier of P0 (22) and P1 (24): P0."""
    states = ["S", "S", "S", "S", "W", "W", "W", "E"]
    courts = [{"S": 2, "W": 1}, {"S": 2, "W": 1}, {"S": 1, "W": 1}]
    s = _cor(states, courts, sizes=[0, 0, 0], last_play=[22, 24, 9])
    _check_result(s, 3, [0])


def test_R404_step3_after_step2_tie_with_one_emptied():
    """R-404 step 3: tied on S and W, only P1 emptied (play 14; P0 has 1 card left, P0 played
    last as 15)."""
    states = ["S", "S", "S", "S", "W", "W", "W", "E"]
    courts = [{"S": 2, "W": 1}, {"S": 2, "W": 1}, {"S": 1}]
    s = _cor(states, courts, sizes=[1, 0, 8], last_play=[15, 14, None])
    _check_result(s, 3, [1])


def test_R404_two_of_three_share_the_win():
    """R-404 / R-405: P0 and P1 tie on every step, nobody emptied: both win (+1/4, +1/4, -1/2)."""
    states = ["S", "S", "S", "S", "W", "W", "W", "E"]
    courts = [{"S": 2, "W": 1}, {"S": 2, "W": 1}, {"S": 1, "W": 5}]
    s = _cor(states, courts)
    _check_result(s, 3, [0, 1])
    assert s.returns() == pytest.approx([0.25, 0.25, -0.5])


def test_R404_three_way_tie_all_share_zero_returns():
    """R-405: a three-way shared win gives everybody 0."""
    states = ["S", "S", "S", "S", "W", "W", "W", "E"]
    courts = [{"S": 2}] * 3
    s = _cor(states, courts)
    _check_result(s, 3, [0, 1, 2])
    assert s.returns() == pytest.approx([0, 0, 0])


def test_R404_two_players_sole_winner_gets_plus_one():
    """R-405: n=2, sole winner +1, loser -1."""
    states = ["S", "S", "S", "S", "W", "W", "W", "E"]
    s = _cor(states, [{"S": 1}, {"S": 3}])
    assert s.returns() == pytest.approx([-1, 1])
    _check_result(s, 2, [1])


def test_R404_no_rank1_followers_in_any_court_falls_to_rank2():
    """R-404 boundary: nobody holds a rank-1 follower (all 0): everyone ties, step 2 rank-2
    decides: P1 with a Welsh follower."""
    states = ["S", "S", "S", "S", "W", "W", "W", "E"]
    s = _cor(states, [{"E": 3}, {"W": 1}])
    _check_result(s, 2, [1])


def test_R404_hand_empty_not_consulted_when_step_one_decides():
    """R-404 (negative): P1 emptied the hand early but P0 has more rank-1 followers: P0 wins."""
    states = ["S", "S", "S", "S", "W", "W", "W", "E"]
    s = _cor(states, [{"S": 3}, {"S": 2}], sizes=[1, 0], last_play=[15, 14])
    _check_result(s, 2, [0])


def test_R404_coronation_via_real_passes_after_eighth_struggle():
    """R-404 / R-304: a real pass-only run to the eighth struggle: the final board gives
    Scottish control of region 7 (Devon) so the game is a coronation won by the court with
    most Scottish (Scots rank 1: 5 regions, W 2, last unstable E none)."""
    s = _scn(
        2,
        ["S", "W", "S", "W", "S", U, "S"],
        [{"S": 3}, {"S": 1, "W": 9}],
        pass_count=1,
        board={7: {"S": 2}},
    )
    s.apply_action(PASS)
    assert s.struggles_resolved == 8 and _unstable(s) == 1
    _check_result(s, 2, [0])


# ================================================================ R-304 ordering


def _both_ways_courts():
    # P0 holds many Scots and no complete set; P1 one complete set.
    return [{"S": 3}, {"S": 1, "W": 1, "E": 1}]


def test_R402_invasion_checked_before_coronation_on_eighth_struggle():
    """R-304 / R-400 / R-402: two earlier unstable regions and the eighth struggle (empty Devon)
    makes the third: invasion. Invasion winner = most sets = P1. (Coronation would rank S first
    -- S controls 4 -- and give P0, with 3 Scots, the win.)"""
    states = ["S", U, "S", "W", U, "S", "S"]
    s = _scn(2, states, _both_ways_courts(), pass_count=1)
    s.apply_action(PASS)
    assert s.struggles_resolved == 8
    assert _unstable(s) == 3
    _check_result(s, 2, [1])


def test_R402_invasion_on_eighth_struggle_tied_followers_variant():
    """R-304: the eighth struggle is a tie (S1 W1 in Devon) which places the third disc:
    invasion again, P1 (one set) wins."""
    states = ["S", U, "S", "W", U, "S", "S"]
    s = _scn(2, states, _both_ways_courts(), pass_count=1, board={7: {"S": 1, "W": 1}})
    s.apply_action(PASS)
    assert _unstable(s) == 3
    _check_result(s, 2, [1])


def test_R404_eighth_struggle_with_only_two_unstable_is_coronation():
    """R-304 (negative of the ordering test): same history but Devon is won by the Scots: two
    unstable only, coronation: rank 1 S, P0's 3 Scots win over P1's 1."""
    states = ["S", U, "S", "W", U, "S", "S"]
    s = _scn(2, states, _both_ways_courts(), pass_count=1, board={7: {"S": 2}})
    s.apply_action(PASS)
    assert _unstable(s) == 2
    _check_result(s, 2, [0])


def test_R402_three_player_invasion_on_eighth_struggle():
    """R-304 / R-402 / R-405: 3 players, invasion at the eighth struggle; P2 has the most sets."""
    states = [U, "S", "W", U, "E", "S", "W"]
    courts = [{"S": 6}, {"S": 2, "W": 2, "E": 1}, {"S": 2, "W": 2, "E": 2}]
    s = _scn(3, states, courts, pass_count=2)
    s.apply_action(PASS)
    assert _unstable(s) == 3 and s.struggles_resolved == 8
    _check_result(s, 3, [2])
