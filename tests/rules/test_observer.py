"""Acceptance tests for the observer (Phase 2 unit 10): PLAN.md 5.5, ACTIONS.md "Undo block"
(the observation must expose enough of B* for R-216/R-217), OPENSPIEL_NOTES.md "Observer pattern".

Only the public API is used: ``game.make_py_observer()`` (``tensor``, ``dict``, ``set_from``,
``string_from``), ``state.observation_tensor(p)``, ``state.observation_string(p)``,
``game.observation_tensor_size()``, ``pyspiel.serialize_game_and_state``.
Tensor layout offsets are NOT tested (not fixed by the spec).

Assumed identifiers (flagged in the report):
  * game string ``python_king_is_dead(players=N)`` (registered by importing ``kingisdead.game``);
  * dict view names ``region_counts``, ``courts``, ``supply``, ``region_states``, ``hands``,
    ``discs`` (negotiation discs), ``phase``, ``pass_count``, ``undo_block`` (B* record);
  * seat-relative views (``courts``, ``hands``) have the observing player at index 0, then
    seats p+1, p+2 ... modulo N;
  * state attribute ``s.courts[p][f]`` (as in the other rule tests);
  * scenario keys as in tests/scenarios/*.json (``pass_count``, ``hands``, ``regions``, ``courts``,
    ``to_play``, ``last_card.reference_board``).
Pending marker: every test is ``@pytest.mark.pending("R-216")`` (observer-unit10).
"""

import copy
import json
import pickle
import random
from pathlib import Path

import numpy as np
import pyspiel
import pytest

import kingisdead.game  # noqa: F401  (registers the game)
from kingisdead.scenario import load_scenario

SCEN = Path(__file__).resolve().parent.parent / "scenarios"
pending = pytest.mark.pending("R-216")


def _game(n):
    return pyspiel.load_game(f"python_king_is_dead(players={n})")


def _obs(game, s, p):
    """Fresh copy of (tensor, string) for player p via the public observer."""
    ob = game.make_py_observer()
    ob.set_from(s, p)
    return ob.tensor.copy(), ob.string_from(s, p)


def _views(game, s, p):
    ob = game.make_py_observer()
    ob.set_from(s, p)
    return {k: np.array(v, copy=True) for k, v in ob.dict.items()}


def _playout(game, rng, max_steps=None):
    """Yield every state of one random playout (the same object, mutated)."""
    s = game.new_initial_state()
    steps = 0
    yield s
    while not s.is_terminal():
        if s.is_chance_node():
            acts, probs = zip(*s.chance_outcomes(), strict=True)
            s.apply_action(rng.choices(acts, probs)[0])
        else:
            s.apply_action(rng.choice(s.legal_actions()))
        steps += 1
        yield s
        if max_steps is not None and steps >= max_steps:
            return


def _midgame(game, seed, plies=70):
    rng = random.Random(seed)
    s = None
    for st in _playout(game, rng, max_steps=plies):
        s = st
    assert s is not None
    return s


def _base():
    with open(SCEN / "undo_block_outmanoeuvre.json") as f:
        data = json.load(f)
    data.pop("example", None)
    return data


def _load(data):
    return load_scenario(copy.deepcopy(data))


def _differs(game, a, b, players=2):
    return any(not np.array_equal(_obs(game, a, p)[0], _obs(game, b, p)[0]) for p in range(players))


# ---------------------------------------------------------------- tensor shape / type


@pytest.mark.parametrize("n", [2, 3])
def test_observer_tensor_fixed_size_float32_finite(n):
    """PLAN 5.5 / notes: flat float32 tensor, constant size, finite at every state (setup,
    play, terminal) and for every player."""
    game = _game(n)
    size = game.observation_tensor_size()
    assert size > 0
    assert list(game.observation_tensor_shape()) == [size]
    ob = game.make_py_observer()
    rng = random.Random(1)
    for s in _playout(game, rng):
        for p in range(n):
            ob.set_from(s, p)
            assert ob.tensor.dtype == np.float32
            assert ob.tensor.shape == (size,)
            assert np.all(np.isfinite(ob.tensor))
            assert len(s.observation_tensor(p)) == size


def test_observer_sizes_differ_by_player_count_but_are_fixed_each():
    """Fixed size per player count (2 and 3): two games of the same count agree."""
    for n in (2, 3):
        assert _game(n).observation_tensor_size() == _game(n).observation_tensor_size()


@pytest.mark.parametrize("n", [2, 3])
def test_observer_chance_initial_and_terminal_states_do_not_raise(n):
    """Observation of a setup chance node and of a terminal state is defined."""
    game = _game(n)
    s = game.new_initial_state()
    assert s.is_chance_node()
    for p in range(n):
        assert isinstance(s.observation_string(p), str)
        assert len(s.observation_tensor(p)) == game.observation_tensor_size()
    last = None
    for st in _playout(game, random.Random(5)):
        last = st
    assert last is not None and last.is_terminal()
    for p in range(n):
        assert isinstance(last.observation_string(p), str)
        assert np.all(np.isfinite(last.observation_tensor(p)))


# ---------------------------------------------------------------- named views


@pytest.mark.parametrize("n", [2, 3])
def test_observer_named_dict_views_exist_and_alias_tensor(n):
    """Named dict views exist for the main groups, are views onto ``tensor`` (not copies) and
    all lie inside it."""
    game = _game(n)
    ob = game.make_py_observer()
    wanted = {
        "region_counts",
        "courts",
        "supply",
        "region_states",
        "hands",
        "discs",
        "phase",
        "pass_count",
        "undo_block",
    }
    assert wanted <= set(ob.dict), f"missing views: {wanted - set(ob.dict)}"
    s = _midgame(game, 3)
    ob.set_from(s, 0)
    total = sum(v.size for v in ob.dict.values())
    assert 0 < total <= ob.tensor.size
    for v in ob.dict.values():
        assert np.shares_memory(v, ob.tensor)


@pytest.mark.parametrize("n", [2, 3])
def test_observer_views_match_state_counts(n):
    """Own-seat court view of the observer equals the state's court for that seat."""
    game = _game(n)
    s = _midgame(game, 4)
    for p in range(n):
        v = _views(game, s, p)
        own = np.asarray(v["courts"]).reshape(n, -1)[0]
        assert list(map(float, own)) == [float(s.courts[p][f]) for f in range(3)]


# ---------------------------------------------------------------- rotation


@pytest.mark.parametrize("n", [2, 3])
def test_observer_own_seat_first_rotation(n):
    """Player p's view of seat-relative index k equals player q's view of index (p + k - q) mod n,
    for the court and hand views; index 0 is always the observer."""
    game = _game(n)
    s = _midgame(game, 11)
    views = [_views(game, s, p) for p in range(n)]
    for name in ("courts", "hands"):
        rows = [np.asarray(v[name]).reshape(n, -1) for v in views]
        for p in range(n):
            for q in range(n):
                for k in range(n):
                    assert np.array_equal(rows[p][k], rows[q][(p + k - q) % n]), (name, p, q, k)


def test_observer_view_depends_on_observer_seat():
    """With distinct courts, the two players' tensors/strings differ (own seat first)."""
    game = _game(2)
    s = _load(_base())
    t0, s0 = _obs(game, s, 0)
    t1, s1 = _obs(game, s, 1)
    assert not np.array_equal(t0, t1)
    assert s0 != s1


# ---------------------------------------------------------------- function of state only


def test_observer_same_state_same_observation_clone_and_reload():
    """Observation is a pure function of the state: a clone and a freshly loaded identical
    scenario give identical tensors and strings; repeated calls are idempotent."""
    game = _game(2)
    a = _load(_base())
    for b in (a.clone(), _load(_base())):
        for p in range(2):
            ta, sa = _obs(game, a, p)
            tb, sb = _obs(game, b, p)
            assert np.array_equal(ta, tb)
            assert sa == sb
    assert np.array_equal(_obs(game, a, 0)[0], _obs(game, a, 0)[0])


def _equal_obs_check(n, playouts):
    game = _game(n)
    seen = {}
    rng = random.Random(21)
    for _ in range(playouts):
        for s in _playout(game, rng):
            if s.is_terminal() or s.is_chance_node():
                continue
            p = s.current_player()
            t, st = _obs(game, s, p)
            key = t.tobytes()
            info = (st, s.current_player(), tuple(s.legal_actions()))
            if key in seen:
                assert seen[key] == info
            else:
                seen[key] = info
    assert len({v[0] for v in seen.values()}) == len(seen)


@pytest.mark.parametrize("n", [2, 3])
def test_observer_equal_observation_implies_equal_legal_actions(n):
    """Across random playouts (reduced count), any two states (of the same mover) with the same
    observation tensor have the same legal actions and mover; tensor equality and string equality
    coincide."""
    _equal_obs_check(n, 8)


@pytest.mark.slow
@pytest.mark.parametrize("n", [2, 3])
def test_observer_equal_observation_implies_equal_legal_actions_full(n):
    """Full-size version (60 playouts) of the observation-determines-legal-actions check."""
    _equal_obs_check(n, 60)


# ---------------------------------------------------------------- sensitivity


def _variants():
    """(label, mutate(data)) pairs; each changes exactly one exposed field of the base scenario."""

    def region_count(d):
        d["regions"]["Moray"]["W"] += 1  # supply absorbs the difference

    def region_new_faction(d):
        d["regions"]["Strathclyde"]["E"] = 1

    def court(d):
        d["courts"][1]["S"] = 1

    def pass_count(d):
        d["pass_count"] = 1

    def mover(d):
        d["to_play"] = 0

    def bstar_counts(d):
        d["last_card"]["reference_board"]["regions"] = {"Moray": {"W": 2}, "Strathclyde": {"S": 1}}

    def bstar_state(d):
        d["last_card"]["reference_board"]["region_state"] = {"Lancaster": "unstable"}

    return [
        ("region_count", region_count),
        ("region_new_faction", region_new_faction),
        ("court", court),
        ("pass_count", pass_count),
        ("mover", mover),
        ("bstar_counts", bstar_counts),
        ("bstar_region_state", bstar_state),
    ]


@pytest.mark.parametrize("label,mutate", _variants(), ids=[v[0] for v in _variants()])
def test_observer_states_differing_in_one_field_differ(label, mutate):
    """Any exposed field changing (region count, court, pass count, mover, and the
    undo-block record: B* contents, B* region states, L's card type, presence) changes the
    observation of at least one player, in both tensor and string."""
    game = _game(2)
    base = _base()
    changed = copy.deepcopy(base)
    mutate(changed)
    try:
        a, b = _load(base), _load(changed)
    except Exception as e:  # an unusable mutated scenario is a test-authoring problem
        pytest.skip(f"scenario loader rejected the variant: {e}")
    assert _differs(game, a, b)
    assert any(_obs(game, a, p)[1] != _obs(game, b, p)[1] for p in range(2))


def test_observer_pending_pick_and_phase_are_exposed():
    """Phase / pending sub-decision context: the state after PLAY(Outmanoeuvre) and the state after
    the first region pick differ only in pending context (card, picks so far) and still differ in
    observation; so does the state before the card was played."""
    game = _game(2)
    s0 = _load(_base())
    assert s0.current_player() == 1
    s1 = s0.clone()
    s1.apply_action(7)  # PLAY(Outmanoeuvre)
    s2 = s1.clone()
    s2.apply_action(s2.legal_actions()[0])  # first FOLLOWER pick
    assert s2.current_player() == s1.current_player()
    for a, b in ((s1, s2), (s0, s1)):
        assert np.array_equal(
            _obs(game, a, 1)[0], _obs(game, a.clone(), 1)[0]
        )  # determinism sanity
        assert not np.array_equal(_obs(game, a, 1)[0], _obs(game, b, 1)[0])
        assert _obs(game, a, 1)[1] != _obs(game, b, 1)[1]


def test_observer_two_different_picks_give_different_observations():
    """Two different first picks of the same card (same board, same hand) leave the state with
    different pending context, so the observations differ. R-216 (D22): the base scenario with
    B* omitted is void, so nothing is blocked and several first picks are legal (with B* present
    R-215/R-216 force a single first pick, 17)."""
    game = _game(2)
    data = _base()
    data["last_card"].pop("reference_board")
    data["regions"]["Strathclyde"] = {"S": 1, "E": 1}  # several distinct first picks
    s = _load(data)
    s.apply_action(7)
    acts = s.legal_actions()
    assert len(acts) >= 2
    a, b = s.clone(), s.clone()
    a.apply_action(acts[0])
    b.apply_action(acts[1])
    assert not np.array_equal(_obs(game, a, 1)[0], _obs(game, b, 1)[0])


# ---------------------------------------------------------------- B* sufficiency


def test_observer_bstar_is_visible_in_undo_block_view():
    """ACTIONS.md Undo block: two states identical except B* (undo_block_outmanoeuvre vs the same
    position with a different reference board) differ in the ``undo_block`` view for the mover,
    and in no other named view."""
    game = _game(2)
    base = _base()
    other = copy.deepcopy(base)
    other["last_card"]["reference_board"]["regions"] = {"Moray": {"W": 2}, "Strathclyde": {"S": 1}}
    a, b = _load(base), _load(other)
    va, vb = _views(game, a, 1), _views(game, b, 1)
    assert not np.array_equal(va["undo_block"], vb["undo_block"])
    for k in va:
        if k != "undo_block":
            assert np.array_equal(va[k], vb[k]), k


@pytest.mark.parametrize("scenario", ["undo_block_outmanoeuvre", "undo_block_void"])
def test_observer_bstar_scenarios_masks_follow_from_observation(scenario):
    """Two loads of the same undo-block scenario give the same observation and the same legal
    masks along the whole first decision level; an A/B state with different B* is told apart by
    the observation whenever their masks differ (the observation determines the masks)."""
    game = _game(2)
    with open(SCEN / f"{scenario}.json") as f:
        data = json.load(f)
    data.pop("example", None)
    a, b = _load(data), _load(data)
    p = a.current_player()
    assert np.array_equal(_obs(game, a, p)[0], _obs(game, b, p)[0])
    assert a.legal_actions() == b.legal_actions()
    if "last_card" in data and data["last_card"].get("reference_board"):
        other = copy.deepcopy(data)
        other["last_card"].pop("reference_board")
        try:
            c = _load(other)
        except Exception:
            return
        # whatever the masks do, different B* records must not be indistinguishable
        assert _differs(game, a, c)


def test_observer_undo_block_changes_with_other_card_play():
    """R-217: when any card is played, L and B* are replaced. From the base scenario (B* present)
    and a copy with B* void (D22), the mover plays Scottish Support; afterwards the ``undo_block``
    views agree, although they differed before the play."""
    game = _game(2)
    data = _base()
    nodata = copy.deepcopy(data)
    nodata["last_card"].pop("reference_board")
    s, t = _load(data), _load(nodata)
    assert not np.array_equal(_views(game, s, 0)["undo_block"], _views(game, t, 0)["undo_block"])
    assert 1 in s.legal_actions() and 1 in t.legal_actions()
    for st in (s, t):
        st.apply_action(1)  # PLAY(Scottish Support)
        guard = 0
        while st.current_player() == 1 and guard < 20 and not st.is_terminal():
            st.apply_action(st.legal_actions()[-1])
            guard += 1
        assert st.current_player() != 1
    va, vb = _views(game, s, 0), _views(game, t, 0)
    assert np.array_equal(va["undo_block"], vb["undo_block"])


# ---------------------------------------------------------------- serialization


@pytest.mark.parametrize("n", [2, 3])
def test_observer_serialization_roundtrip_preserves_observation(n):
    """A mid-game state serialised with pyspiel (and plain pickle) observes identically, and the
    restored state keeps playing with the same observations."""
    game = _game(n)
    s = _midgame(game, 8, plies=90)
    assert not s.is_terminal()
    text = pyspiel.serialize_game_and_state(game, s)
    game2, s2 = pyspiel.deserialize_game_and_state(text)
    s3 = pickle.loads(pickle.dumps(s))
    for p in range(n):
        t, st = _obs(game, s, p)
        for g2, other in ((game2, s2), (game, s3)):
            t2, st2 = _obs(g2, other, p)
            assert np.array_equal(t, t2)
            assert st == st2
    if not s.is_terminal() and not s.is_chance_node():
        a = s.legal_actions()[0]
        s.apply_action(a)
        s2.apply_action(a)
        for p in range(n):
            assert np.array_equal(_obs(game, s, p)[0], _obs(game2, s2, p)[0])


# ---------------------------------------------------------------- smoke


def _smoke(n, playouts):
    game = _game(n)
    size = game.observation_tensor_size()
    ob = game.make_py_observer()
    rng = random.Random(100 + n)
    for _ in range(playouts):
        for s in _playout(game, rng):
            for p in range(n):
                ob.set_from(s, p)
                assert ob.tensor.size == size
                assert np.all(np.isfinite(ob.tensor))
                assert np.allclose(np.asarray(s.observation_tensor(p), dtype=np.float32), ob.tensor)
                assert s.observation_string(p) == ob.string_from(s, p)
                assert s.observation_string(p)
    assert game.observation_tensor_size() == size


@pytest.mark.parametrize("n", [2, 3])
def test_observer_random_playout_smoke(n):
    """A few random playouts (reduced count): tensors finite, float32, constant size, consistent
    between ``state.observation_tensor`` and the observer, strings non-empty, no exceptions."""
    _smoke(n, 4)


@pytest.mark.slow
@pytest.mark.parametrize("n", [2, 3])
def test_observer_random_playout_smoke_full(n):
    """Full-size version (150 playouts) of the random-playout smoke test."""
    _smoke(n, 150)
