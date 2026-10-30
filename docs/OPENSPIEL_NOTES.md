# OpenSpiel 2.0.2 notes for a Python game

Findings from the Phase 0 spike. Everything here was checked against the installed 2.0.2 source
(`.venv/lib/python3.12/site-packages/open_spiel/`) and exercised by `tests/test_openspiel_api.py`
using the toy game `tests/support/toy_chance_game.py` (`python_kid_toy`, shaped like our game:
2-3 players, bag-draw setup chance nodes, two consecutive decisions by one player, shared win).

## Registration

```python
import pyspiel

GAME_TYPE = pyspiel.GameType(
    short_name="python_kid_toy",
    long_name="...",
    dynamics=pyspiel.GameType.Dynamics.SEQUENTIAL,
    chance_mode=pyspiel.GameType.ChanceMode.EXPLICIT_STOCHASTIC,
    information=pyspiel.GameType.Information.PERFECT_INFORMATION,
    utility=pyspiel.GameType.Utility.ZERO_SUM,
    reward_model=pyspiel.GameType.RewardModel.TERMINAL,
    min_num_players=2,
    max_num_players=3,
    provides_information_state_string=False,
    provides_information_state_tensor=False,
    provides_observation_string=True,
    provides_observation_tensor=True,
    parameter_specification={"players": 2},  # name -> default value (defines the type)
)


class MyGame(pyspiel.Game):
    def __init__(self, params=None):
        params = dict(params or {})
        n = int(params.get("players", 2))
        info = pyspiel.GameInfo(
            num_distinct_actions=...,
            max_chance_outcomes=...,
            num_players=n,
            min_utility=-1.0 / (n - 1),
            max_utility=1.0,
            utility_sum=0.0,
            max_game_length=...,
        )  # player decisions only, see below
        super().__init__(GAME_TYPE, info, params)


pyspiel.register_game(GAME_TYPE, MyGame)  # at import time
```

- `pyspiel.load_game("python_kid_toy(players=3)")` works once the module has been imported (the
  import is what registers it; `open_spiel.python.games` does this for the bundled games).
  Missing params fall back to `parameter_specification` defaults; `get_parameters()` returns
  `{"players": 3}`. Unknown params raise `pyspiel.SpielError`.
- `min_num_players`/`max_num_players` are NOT enforced by `load_game` for Python games
  (`players=4` loads fine). Validate in `Game.__init__` (we raise `ValueError`, which propagates).
- `GameInfo.num_players` must be set from the parameter, so `GameInfo` is built inside
  `__init__`, not at module level, when the player count is a parameter
  (the iterated-prisoner's-dilemma example does the same).
- Registering the same game twice does not raise (harmless under pytest's importlib mode).
- Python games are "global Python objects": game and state classes must stay importable for
  pickling (see serialization).

## max_game_length excludes chance nodes

`GameInfo.max_game_length` is the maximum number of *player decisions* summed over players.
`pyspiel.random_sim_test` enforces it: it counts only non-chance actions and fails with
`game_length <= game.MaxGameLength()` otherwise. Chance nodes are bounded separately by
`Game.max_chance_nodes_in_history()`, which defaults to `max_game_length` (a loose bound). A Python
game may override it as a method on the `Game` subclass (`PyGame` forwards it; the toy game does).
Derived: `max_history_length() = max_game_length + max_chance_nodes_in_history`, and
`max_move_number()` is the same sum. Declare both exactly so tensors/buffers sized from them
(e.g. in RL code) are correct. Counting setup chance nodes into
`max_game_length` (as PLAN.md originally assumed) is wrong in 2.0.2.

## State API (what `pyspiel.State` subclasses implement)

Required: `current_player()`, `_legal_actions(player)`, `_apply_action(action)`,
`_action_to_string(player, action)`, `is_terminal()`, `returns()`, `__str__`.
Chance games also: `chance_outcomes()` returning `[(action, prob), ...]`. Note the underscore
prefixes: you implement `_legal_actions`/`_apply_action`/`_action_to_string`; callers use the
public `legal_actions()`/`apply_action()`/`action_to_string()`.

- `current_player()` returns `pyspiel.PlayerId.CHANCE` (-1) for chance nodes and
  `pyspiel.PlayerId.TERMINAL` (-4) at the end, else the seat. A player acting twice in a row is
  simply `current_player()` returning the same seat for consecutive states.
- `_legal_actions` must be sorted ascending, empty at terminal. `legal_actions()` at a chance
  node returns the chance action ids (the `chance_outcomes()` keys).
- `chance_outcomes()` probabilities may depend on state (bag counts); omit zero-probability
  outcomes. Chance actions share the action-id space with nothing else: ids only need to be
  `< max_chance_outcomes`, and apply via `apply_action` like any other action. The history
  records them as `-1:<action>`.
- `returns()` must be defined before terminal too; return zeros. `rewards()` defaults to zeros.
  With `RewardModel.TERMINAL` MCTS and `random_sim_test` only read returns at the end.
- `clone()` has a working default for Python states and the clone is independent (the toy game's
  lists are not shared); no override is needed for correctness. We may override for speed later.
- `history()`, `move_number()`, `is_chance_node()`, `legal_actions_mask()` etc. are provided.
- `information_state_string/tensor` fall back to the observation even when
  `provides_information_state_*` is False; harmless, don't rely on it.
- Optional (tic_tac_toe shows them): `_to_struct`, `_action_to_struct`, `_struct_to_actions`,
  `_to_observation_struct`, and `new_initial_state(self, state=None)` for struct/JSON round
  trips. Not needed for Kuhn-style games; skip unless the server wants them.

## Chance outcomes and serialization

- Sampling is the caller's job: tests and bots pick from `chance_outcomes()` by probability.
  MCTS handles chance nodes inside its tree, but `MCTSBot.step()` on a chance root returns
  `pyspiel.INVALID_ACTION` (-1) and does nothing, so the driver must apply chance itself.
- `state.serialize()` (default on `PyState`) returns
  `history=-1:0,-1:1\nmove_number=2\n__dict__=<base64 pickle of state.__dict__>`.
  `pyspiel.serialize_game_and_state(game, state)` wraps it with the game string, and
  `pyspiel.deserialize_game_and_state(text)` rebuilds the game via `load_game` and the state from
  the pickled `__dict__`. Consequence: every attribute on the state must be picklable. The deserialized
  state keeps playing identically (tested). `pickle.dumps` of states and games also works.
- Playthrough text (`generate_playthrough`) only emits `SerializeState()` for
  `SAMPLED_STOCHASTIC` games; ours is `EXPLICIT_STOCHASTIC`.

## Observer pattern (PyObserver)

`Game.make_py_observer(self, iig_obs_type=None, params=None)` returns an object with:

- `tensor`: one flat `np.float32` array of constant size;
- `dict`: name -> reshaped *view* onto `tensor` (so write through the views, never rebind them);
- `set_from(state, player)`: refill `tensor` (call `tensor.fill(0)` first);
- `string_from(state, player)`: the observation string.

`iig_obs_type` is `None` for the default observation; imperfect-information games branch on its
`public_info`/`private_info`/`perfect_recall` fields. For a perfect-information game, ignore it
and return the same observer. `params` must be falsy unless you support observation params.
`state.observation_tensor(p)`, `state.observation_string(p)`, `game.observation_tensor_size()` and
`open_spiel.python.observation.make_observation(game)` (-> `.set_from`, `.tensor`, `.dict`,
`.string_from`) all go through it. `game.observation_tensor_shape()` is flat (`[size]`); the named
shapes appear in playthroughs (`ObservationTensor(0).hands`) via `tensors_info`.
`IIGObserverForPublicInfoGame` (observation.py) is a helper for fixed-public-info games; not needed.

## Test and bot call signatures

```python
pyspiel.random_sim_test(
    game,
    num_sims,
    serialize,
    verbose,
    mask_test=True,
    state_checker_fn=...,
    mean_field_population=-1,
    observer=None,
    specific_initial_state=None,
)
# serialize=True exercises serialize/deserialize (works for Python games)

from open_spiel.python.algorithms import mcts

bot = mcts.MCTSBot(
    game,
    uct_c,
    max_simulations,
    evaluator,
    solve=True,
    random_state=None,
    child_selection_fn=...,
    dirichlet_noise=None,
    verbose=False,
    dont_return_chance_node=False,
)
evaluator = mcts.RandomRolloutEvaluator(n_rollouts=1, random_state=None, max_length=None)
action = bot.step(state)  # at player nodes only
policy, action = bot.step_with_policy(state)

from open_spiel.python.algorithms import generate_playthrough

text = generate_playthrough.playthrough(
    game_string, action_sequence, seed=None, alsologtostdout=False, observation_params_string=None
)
```

- `MCTSBot` requires TERMINAL rewards and SEQUENTIAL dynamics; it needs `game.max_utility()`.
  Zero-sum n-player is handled as max^n. It plays consecutive same-player decisions fine (each
  `step` call searches from the current state). With `solve=True` terminal children are proven,
  so a last-move choice is found even with ~30 simulations.
- `generate_playthrough` takes a game *string*, so the game must be registered (module imported)
  first; `action_sequence=[]` means fully random with `seed`. Same seed gives identical text.
  Golden playthroughs for kingisdead will need chance outcomes seeded the same way.
- Speed: Python games are slow in MCTS; the toy runs 15-simulation searches instantly, but real
  Phase 5 budgets need profiling. `state.clone()` is on the MCTS hot path.

## Differences from 1.x and surprises

- `max_game_length` excludes chance nodes (see above); `max_chance_nodes_in_history()` can be overridden.
- The 2.0.2 example games (tic_tac_toe) show optional struct APIs (`_to_struct`,
  `new_initial_state(state=None)`); I did not compare with 1.x, but Kuhn-style games need none of it.
- `load_game` does not enforce min/max player counts for Python games.
- Python state serialization is a pickle of `__dict__`; no need to hand-write `serialize`.
- `random_sim_test` is a good guard: it fails loudly on a wrong `max_game_length`.

## Template for kingisdead/game.py

```python
GAME_TYPE = pyspiel.GameType(short_name="python_king_is_dead", ... parameter_specification={"players": 2})

class KingIsDeadGame(pyspiel.Game):
    __init__(params)                    # validate players in 2..3, build GameInfo, super().__init__
    max_chance_nodes_in_history()       # setup draws only (optional override, exact bound)
    new_initial_state()
    make_py_observer(iig_obs_type=None, params=None)

class KingIsDeadState(pyspiel.State):
    __init__(game)                      # picklable attributes only
    current_player()                    # CHANCE / TERMINAL / seat; same seat for sub-steps
    _legal_actions(player)              # sorted; depends on phase machine
    chance_outcomes()                   # [(action, prob)] from remaining counts
    _apply_action(action)               # dispatches chance vs player, advances phase
    _action_to_string(player, action)
    is_terminal()
    returns()                           # zeros until terminal; shared win formula afterwards
    __str__()
    clone()                             # optional speed override

class KingIsDeadObserver:               # tensor (float32 flat), dict (views), set_from, string_from
pyspiel.register_game(GAME_TYPE, KingIsDeadGame)    # at import of kingisdead.game
```
