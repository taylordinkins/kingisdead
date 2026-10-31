"""Acceptance tests for setup and the game skeleton: R-007, R-010..R-015, R-100.

Public OpenSpiel API is used wherever possible. The tests depend on this small, explicitly
assumed set of ``KingIsDeadState`` attributes (all read through ``_snap`` so there is one place
to adapt them; the spec does not fix the names):
  region_counts[r][f]    followers of faction f on region r (8 x 3)
  courts[p][f]           followers of faction f in player p's court
  supply[f]              followers of faction f in the supply (during setup: the bag)
  slot_regions[i]        region shown on the card in slot i+1 (None until placed)
  region_states[r]       one of constants.REGION_OPEN / REGION_CONTROLLED / REGION_UNSTABLE
  negotiation_discs[p]   region index carrying player p's spent disc, None if unspent
  pass_count             consecutive passes
  struggles_resolved     number of struggles resolved so far
  hands[p]               mapping card id (1..7) -> copies still in hand
  plays_total            number of cards played so far
Other assumptions:
  * chance outcome ids are the identity encoding of ACTIONS section 3: region index r for the
    region-card picks, faction index f for draws (decision-id space is unrelated).
  * ``kingisdead.game`` registers ``python_king_is_dead`` on import.
  * ``kingisdead.scenario.load_scenario(source)`` takes a path or an already parsed dict and
    returns a state; ``ValueError`` for a rejected scenario.
The setup chance sequence for a scenario is computed here, independently, from SCENARIOS.md 2.
"""

import json
import random
from pathlib import Path

import pyspiel
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
FACT = {"S": 0, "W": 1, "E": 2}
HOME = {0: 0, 1: 4, 2: 6}  # faction -> home region (R-003)
POOL = {2: 16, 3: 18}


def _load(players=2):
    import kingisdead.game  # noqa: F401  (registers the game)

    return pyspiel.load_game(f"python_king_is_dead(players={players})")


def _snap(s):
    return {
        "regions": [list(map(int, row)) for row in s.region_counts],
        "courts": [list(map(int, row)) for row in s.courts],
        "supply": list(map(int, s.supply)),
        "slots": list(s.slot_regions),
    }


def _chance_sequence(data):
    """SCENARIOS.md section 2: scenario dict -> list of chance outcomes."""
    seq = [REGIONS.index(n) for n in data["slots"]]
    for court in data["courts"]:
        seq += [FACT[k] for k in "SWE" for _ in range(court.get(k, 0))]
    for r, name in enumerate(REGIONS):
        counts = dict(data["regions"].get(name, {}))
        for f, k in enumerate("SWE"):
            if HOME[f] == r:
                counts[k] = counts.get(k, 0) - 2
        seq += [FACT[k] for k in "SWE" for _ in range(counts.get(k, 0))]
    return seq


def _run_scenario_setup():
    data = json.loads((SCEN / "setup_basic.json").read_text())
    game = _load(data["players"])
    s = game.new_initial_state()
    for o in _chance_sequence(data):
        assert s.is_chance_node()
        assert o in s.legal_actions()
        s.apply_action(o)
    return data, game, s


def _random_setup(players, seed):
    rng = random.Random(seed)
    game = _load(players)
    s = game.new_initial_state()
    states = [s.clone()]
    n = 0
    while s.is_chance_node():
        outs = s.chance_outcomes()
        a = rng.choices([o for o, _ in outs], weights=[p for _, p in outs])[0]
        s.apply_action(a)
        n += 1
        states.append(s.clone())
    return game, s, n, states


def _conserved(s, players):
    snap = _snap(s)
    for f in range(3):
        total = (
            sum(row[f] for row in snap["regions"])
            + sum(row[f] for row in snap["courts"])
            + snap["supply"][f]
        )
        if total != POOL[players] or snap["supply"][f] < 0:
            return False
    return True


# ---------------------------------------------------------------- R-007


@pytest.mark.parametrize("players", [2, 3])
def test_R007_supported_player_counts_load(players):
    """R-007: 2 and 3 players are accepted when the game is created."""
    game = _load(players)
    assert game.num_players() == players


@pytest.mark.parametrize("players", [0, 1, 4, 5, -2])
def test_R007_other_player_counts_rejected(players):
    """R-007: any other count (including 4, deferred to Phase 6) is rejected at creation."""
    import kingisdead.game  # noqa: F401

    with pytest.raises((ValueError, pyspiel.SpielError)):
        pyspiel.load_game(f"python_king_is_dead(players={players})")


def test_R007_default_is_two_players():
    """R-007 / task: the `players` parameter defaults to 2."""
    import kingisdead.game  # noqa: F401

    assert pyspiel.load_game("python_king_is_dead").num_players() == 2


@pytest.mark.parametrize("players,nodes", [(2, 38), (3, 40)])
def test_R007_game_info(players, nodes):
    """R-007, ACTIONS 2/3: 40 actions, 8 chance outcomes, explicit chance, setup node bound."""
    game = _load(players)
    assert game.num_distinct_actions() == 40
    assert game.max_chance_outcomes() == 8
    assert game.get_type().chance_mode == pyspiel.GameType.ChanceMode.EXPLICIT_STOCHASTIC
    assert game.max_chance_nodes_in_history() == nodes


# ---------------------------------------------------------------- R-010


def test_R010_first_node_is_chance_with_uniform_regions():
    """R-010: setup starts with a chance node uniform over the 8 regions."""
    s = _load().new_initial_state()
    assert s.is_chance_node()
    outs = s.chance_outcomes()
    assert sorted(o for o, _ in outs) == list(range(8))
    assert all(p == pytest.approx(1 / 8) for _, p in outs)


def test_R010_picks_fill_slots_in_order_and_exclude_placed_regions():
    """R-010: picks go to slot 1..8 in turn; each pick is uniform over regions not yet placed."""
    s = _load().new_initial_state()
    order = [3, 0, 7, 5, 1, 6, 2, 4]
    for i, r in enumerate(order):
        outs = s.chance_outcomes()
        assert sorted(o for o, _ in outs) == sorted(set(range(8)) - set(order[:i]))
        assert all(p == pytest.approx(1 / (8 - i)) for _, p in outs)
        assert s.legal_actions() == sorted(o for o, _ in outs)
        s.apply_action(r)
        assert [x for x in _snap(s)["slots"] if x is not None] == order[: i + 1]
    assert _snap(s)["slots"] == order


def test_R010_placed_region_is_not_legal_again():
    """R-010 (negative): a region already assigned to a slot cannot be picked again."""
    s = _load().new_initial_state()
    s.apply_action(2)
    assert 2 not in s.legal_actions()
    with pytest.raises((ValueError, RuntimeError, pyspiel.SpielError)):
        s.apply_action(2)


def test_R010_no_negotiation_disc_at_setup():
    """R-010: no card has a negotiation disc after setup."""
    _, _, s = _run_scenario_setup()
    assert all(d is None for d in s.negotiation_discs)


def test_R010_slots_are_permutation_in_random_setups():
    """R-010: any completed setup has a permutation of the 8 regions in the slots."""
    for seed in range(10):
        _, s, _, _ = _random_setup(2, seed)
        assert sorted(_snap(s)["slots"]) == list(range(8))


# ---------------------------------------------------------------- R-011


@pytest.mark.parametrize("players", [2, 3])
def test_R011_home_followers_present_before_any_draw(players):
    """R-011: Moray 2 S, Gwynedd 2 W, Essex 2 E are in place before any random draw."""
    s = _load(players).new_initial_state()
    snap = _snap(s)
    assert snap["regions"][0] == [2, 0, 0]
    assert snap["regions"][4] == [0, 2, 0]
    assert snap["regions"][6] == [0, 0, 2]
    for r in (1, 2, 3, 5, 7):
        assert snap["regions"][r] == [0, 0, 0]
    assert all(c == [0, 0, 0] for c in snap["courts"])


@pytest.mark.parametrize("players", [2, 3])
def test_R011_home_followers_come_out_of_the_pool(players):
    """R-011: the 6 home followers leave the pool: supply (bag) = pool - 2 per faction."""
    s = _load(players).new_initial_state()
    assert _snap(s)["supply"] == [POOL[players] - 2] * 3


# ---------------------------------------------------------------- R-012


def test_R012_first_court_draw_probabilities_2p():
    """R-012: 2 players, bag has 14 of each faction: first court draw is 1/3 each."""
    s = _load(2).new_initial_state()
    for r in range(8):
        s.apply_action(r)
    outs = dict(s.chance_outcomes())
    assert sorted(outs) == [0, 1, 2]
    assert all(p == pytest.approx(1 / 3) for p in outs.values())


def test_R012_draw_probability_is_proportional_to_remaining_bag():
    """R-012: after two Scottish are drawn the next draw is 12/40, 14/40, 14/40 (2 players)."""
    s = _load(2).new_initial_state()
    for r in range(8):
        s.apply_action(r)
    s.apply_action(0)
    s.apply_action(0)
    outs = dict(s.chance_outcomes())
    assert outs[0] == pytest.approx(12 / 40)
    assert outs[1] == pytest.approx(14 / 40)
    assert outs[2] == pytest.approx(14 / 40)
    assert _snap(s)["supply"] == [12, 14, 14]


def test_R012_court_draws_go_to_players_in_seat_order():
    """R-012: seat 0 draws two, then seat 1 (then seat 2), 2 draws per player."""
    s = _load(3).new_initial_state()
    for r in range(8):
        s.apply_action(r)
    for f in (0, 0, 1, 1, 2, 2):
        s.apply_action(f)
    assert _snap(s)["courts"] == [[2, 0, 0], [0, 2, 0], [0, 0, 2]]


def test_R012_court_draws_come_before_region_fill():
    """R-012/R-013: while court draws are pending, no non-home region has followers."""
    s = _load(2).new_initial_state()
    for r in range(8):
        s.apply_action(r)
    for f in (0, 1, 2):
        s.apply_action(f)  # 3 of 4 court draws
        snap = _snap(s)
        for r in (1, 2, 3, 5, 7):
            assert snap["regions"][r] == [0, 0, 0]
    assert _snap(s)["courts"][0] == [1, 1, 0]
    assert _snap(s)["courts"][1] == [0, 0, 1]


@pytest.mark.parametrize("players,draws", [(2, 4), (3, 6)])
def test_R012_court_draw_count(players, draws):
    """R-012: exactly 2 draws per player, so the first region-fill draw is node 8 + draws + 1."""
    s = _load(players).new_initial_state()
    for r in range(8):
        s.apply_action(r)
    for _ in range(draws):
        s.apply_action(0)
    snap = _snap(s)
    assert sum(sum(c) for c in snap["courts"]) == draws
    assert all(sum(c) == 2 for c in snap["courts"])
    # next draw lands in a region, not a court
    s.apply_action(1)
    snap2 = _snap(s)
    assert sum(sum(c) for c in snap2["courts"]) == draws
    assert snap2["regions"][0] == [2, 1, 0]


# ---------------------------------------------------------------- R-013


def _to_fill_start(players=2):
    s = _load(players).new_initial_state()
    for r in range(8):
        s.apply_action(r)
    for _ in range(2 * players):
        s.apply_action(0)
    return s


def test_R013_fill_goes_region_0_first_and_tops_up_to_four():
    """R-013: Moray (index 0) is filled first, 2 draws bring it from 2 to 4."""
    s = _to_fill_start()
    s.apply_action(1)
    assert _snap(s)["regions"][0] == [2, 1, 0]
    s.apply_action(2)
    assert _snap(s)["regions"][0] == [2, 1, 1]
    s.apply_action(1)  # next draw goes to Strathclyde, not Moray
    snap = _snap(s)
    assert snap["regions"][0] == [2, 1, 1]
    assert snap["regions"][1] == [0, 1, 0]


def test_R013_non_home_region_takes_four_draws_then_next_region():
    """R-013: Strathclyde needs 4 draws; the fifth goes to Lancaster."""
    s = _to_fill_start()
    for f in (1, 1):
        s.apply_action(f)  # Moray done
    for f in (1, 1, 2, 2):
        s.apply_action(f)
    snap = _snap(s)
    assert snap["regions"][1] == [0, 2, 2]
    assert snap["regions"][2] == [0, 0, 0]
    s.apply_action(1)
    assert _snap(s)["regions"][2] == [0, 1, 0]


def test_R013_home_regions_in_the_middle_need_two_draws():
    """R-013: Gwynedd (idx 4) and Essex (idx 6) receive 2 draws each."""
    s = _to_fill_start()
    for _ in range(2 + 4 + 4 + 4):  # Moray..Northumbria
        s.apply_action(1)
    assert _snap(s)["regions"][3] == [0, 4, 0]
    assert _snap(s)["regions"][4] == [0, 2, 0]
    s.apply_action(2)
    s.apply_action(2)
    assert _snap(s)["regions"][4] == [0, 2, 2]
    s.apply_action(0)
    assert _snap(s)["regions"][5] == [1, 0, 0]


@pytest.mark.parametrize("players,nodes", [(2, 38), (3, 40)])
def test_R013_chance_node_count_and_post_fill_state(players, nodes):
    """R-013, ACTIONS 3: 38 (2p) or 40 (3p) chance nodes; every region ends with exactly 4."""
    for seed in range(5):
        _, s, n, _ = _random_setup(players, seed)
        assert n == nodes
        assert all(sum(row) == 4 for row in _snap(s)["regions"])


def test_R013_fill_draw_probabilities_use_remaining_bag():
    """R-013: fill draws use the same bag distribution (remaining supply counts)."""
    s = _to_fill_start()  # courts took 4 Scottish: bag S=10, W=14, E=14
    outs = dict(s.chance_outcomes())
    assert outs[0] == pytest.approx(10 / 38)
    assert outs[1] == pytest.approx(14 / 38)
    s.apply_action(0)
    outs = dict(s.chance_outcomes())
    assert outs[0] == pytest.approx(9 / 37)
    assert outs[2] == pytest.approx(14 / 37)


def test_R013_exhausted_faction_has_no_outcome():
    """R-013 / R-012 (boundary): a faction whose bag count is 0 is not offered as an outcome.

    In 2 players the bag has 14 S; after 14 Scottish draws none remain.
    """
    s = _load(2).new_initial_state()
    for r in range(8):
        s.apply_action(r)
    for _ in range(4):
        s.apply_action(0)  # court draws, bag S=10
    for _ in range(10):
        s.apply_action(0)  # Moray takes 2, Strathclyde 4, Lancaster 4: bag S=0
    outs = dict(s.chance_outcomes())
    assert 0 not in outs
    assert sum(outs.values()) == pytest.approx(1.0)
    assert 0 not in s.legal_actions()


# ---------------------------------------------------------------- R-014


def test_R014_scenario_sequence_reaches_setup_basic_position():
    """R-014 / SCENARIOS 2: applying the derived chance sequence yields the scenario position."""
    data, _, s = _run_scenario_setup()
    snap = _snap(s)
    for r, name in enumerate(REGIONS):
        expect = [data["regions"][name].get(k, 0) for k in "SWE"]
        assert snap["regions"][r] == expect
    assert snap["courts"] == [[c.get(k, 0) for k in "SWE"] for c in data["courts"]]
    assert snap["slots"] == [REGIONS.index(n) for n in data["slots"]]
    assert sum(snap["supply"]) == 12


@pytest.mark.parametrize("players,supply", [(2, 12), (3, 16)])
def test_R014_supply_size(players, supply):
    """R-014: supply holds 12 (2p) or 16 (3p) followers after setup."""
    for seed in range(5):
        _, s, _, _ = _random_setup(players, seed)
        assert sum(_snap(s)["supply"]) == supply
        assert all(sum(c) == 2 for c in _snap(s)["courts"])


def test_R014_setup_basic_supply_is_5_3_4():
    """R-014 + setup_basic.json: supply = pool - regions - courts = (S5, W3, E4)."""
    _, _, s = _run_scenario_setup()
    assert _snap(s)["supply"] == [5, 3, 4]


def test_R014_board_discs_and_counters():
    """R-014: all regions open, no instability disc, discs unused, counters zero, not terminal."""
    from kingisdead import constants

    _, _, s = _run_scenario_setup()
    assert not s.is_terminal()
    assert not s.is_chance_node()
    assert all(x == constants.REGION_OPEN for x in s.region_states)
    assert all(d is None for d in s.negotiation_discs)
    assert s.pass_count == 0
    assert s.struggles_resolved == 0
    assert s.plays_total == 0
    assert s.returns() == [0.0, 0.0]


def test_R014_hands_are_the_starting_hand():
    """R-014 / R-008: every hand has 2 Assemble and 1 of each other card."""
    _, _, s = _run_scenario_setup()
    for hand in s.hands:
        assert {c: hand.get(c, 0) for c in range(1, 8)} == {
            1: 1,
            2: 1,
            3: 1,
            4: 2,
            5: 1,
            6: 1,
            7: 1,
        }


def test_R014_legal_actions_at_first_turn():
    """R-014 / ACTIONS 4: player 0 may pass or play any of the 7 card types."""
    _, _, s = _run_scenario_setup()
    assert s.legal_actions() == [0, 1, 2, 3, 4, 5, 6, 7]


def test_R014_no_chance_node_remains_after_setup():
    """R-014 (negative): once setup is complete the state is not a chance node."""
    _, s, _, _ = _random_setup(3, 1)
    assert not s.is_chance_node()
    assert s.current_player() >= 0


def test_R014_scenario_loader_matches_chance_sequence():
    """R-014 / SCENARIOS: scenario.load_scenario of a setup scenario equals the sequence result."""
    from kingisdead import scenario

    _, _, built = _run_scenario_setup()
    loaded = scenario.load_scenario(SCEN / "setup_basic.json")
    assert _snap(loaded) == _snap(built)
    assert loaded.current_player() == built.current_player() == 0
    assert loaded.legal_actions() == built.legal_actions()


def test_R014_scenario_loader_rejects_invalid_setup():
    """R-014 / SCENARIOS V11 (negative): a setup scenario with a 5-follower region is rejected."""
    from kingisdead import scenario

    data = json.loads((SCEN / "setup_basic.json").read_text())
    data["regions"]["Strathclyde"] = {"S": 2, "W": 2, "E": 1}
    with pytest.raises(ValueError):
        scenario.load_scenario(data)


# ---------------------------------------------------------------- R-015


@pytest.mark.parametrize("players", [2, 3])
def test_R015_conservation_at_every_setup_node(players):
    """R-015: per faction, regions + courts + supply = pool at every chance node of setup."""
    for seed in range(5):
        _, _, _, states = _random_setup(players, seed)
        assert all(_conserved(st, players) for st in states)


def test_R015_conservation_after_setup_and_passes():
    """R-015: still holds after setup and after a run of passes (3p) resolves a struggle."""
    _, s, _, _ = _random_setup(3, 7)
    for _ in range(3):
        assert _conserved(s, 3)
        s.apply_action(0)
    assert _conserved(s, 3)


def test_R015_home_regions_only_in_pool():
    """R-015 (negative): placing home followers does not create followers (pool unchanged)."""
    s = _load(2).new_initial_state()
    assert _conserved(s, 2)
    assert sum(_snap(s)["supply"]) == 42


# ---------------------------------------------------------------- R-100


def test_R100_setup_nodes_are_chance_then_player_zero_acts():
    """R-100 / R-014: chance player during setup, then seat 0 is first to act."""
    game = _load(3)
    s = game.new_initial_state()
    assert s.current_player() == pyspiel.PlayerId.CHANCE
    rng = random.Random(0)
    while s.is_chance_node():
        outs = s.chance_outcomes()
        s.apply_action(rng.choices([o for o, _ in outs], weights=[p for _, p in outs])[0])
    assert s.current_player() == 0


def test_R100_passes_advance_in_seat_order_3p():
    """R-100 / R-103: 3 players: after passes by 0 and 1, player 2 is to act."""
    _, s, _, _ = _random_setup(3, 3)
    seq = []
    for _ in range(2):
        seq.append(s.current_player())
        s.apply_action(0)
    seq.append(s.current_player())
    assert seq == [0, 1, 2]
    assert s.pass_count == 2


def test_R100_wraps_after_struggle_to_player_after_last_passer():
    """R-100 / R-105: 3 players all pass -> struggle -> player 0 acts (after last passer 2)."""
    _, s, _, _ = _random_setup(3, 3)
    for _ in range(3):
        s.apply_action(0)
    assert s.pass_count == 0
    assert s.struggles_resolved == 1
    assert s.current_player() == 0


def test_R100_two_player_wrap():
    """R-100: 2 players: 0 passes, 1 passes -> struggle, player 0 is next."""
    _, s, _, _ = _random_setup(2, 3)
    assert s.current_player() == 0
    s.apply_action(0)
    assert s.current_player() == 1
    s.apply_action(0)
    assert s.current_player() == 0


def test_R100_card_play_passes_turn_to_next_seat():
    """R-100 / R-102: after player 0 plays a card and finishes its sub-steps, player 1 acts."""
    _, _, s = _run_scenario_setup()
    s.apply_action(4)  # Assemble
    guard = 0
    while s.current_player() == 0:
        s.apply_action(s.legal_actions()[0])
        guard += 1
        assert guard < 10
    assert s.current_player() == 1


def test_R100_exactly_one_mover_with_legal_actions():
    """R-100 (negative): at a non-terminal decision node the mover is a real seat with actions."""
    _, s, _, _ = _random_setup(3, 5)
    assert 0 <= s.current_player() < 3
    assert len(s.legal_actions()) >= 1
    assert s.legal_actions(s.current_player()) == s.legal_actions()
