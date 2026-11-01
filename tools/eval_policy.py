"""Evaluate a trained checkpoint (greedy argmax over legal actions) against built-in bots.

Usage: uv run python -m tools.eval_policy --checkpoint runs/ppo-main/best.pt \
    --opponents random heuristic mcts:100 --games 300 --seed 200 --workers 6 --json out.json
Per-opponent game counts: --games-for mcts:100=100. Seats rotate by game index; ties are shared
exactly as in tools/tournament.py. Requires the optional `train` dependency group (torch).
"""

import argparse
import json
import random
import sys
import time
from multiprocessing import Pool
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pyspiel  # noqa: E402

import kingisdead.game  # noqa: E402,F401
from server.bots import bot_rng, get_bot, is_valid_seat_type  # noqa: E402
from tools.tournament import TIE_CONVENTION, _git_commit, game_seed, wilson  # noqa: E402

_NET_CACHE: dict[str, Any] = {}


def _net(path: str) -> Any:
    if path not in _NET_CACHE:
        import torch

        from kingisdead.rl.checkpoint import load_checkpoint

        torch.set_num_threads(1)
        _NET_CACHE[path] = load_checkpoint(path)[0]
    return _NET_CACHE[path]


def play_one(checkpoint: str, opponent: str, seed: int, index: int) -> dict:
    """Policy is slot 0, opponent slot 1; the policy sits in seat index % 2."""
    from kingisdead.rl.env import features, legal_mask

    net = _net(checkpoint)
    seat_of = [index % 2, (index + 1) % 2]
    slot_of_seat = {s: b for b, s in enumerate(seat_of)}
    gseed = game_seed(seed, index)
    state = pyspiel.load_game("python_king_is_dead(players=2)").new_initial_state()
    opp = get_bot(opponent)
    hist = 0
    think = [0.0, 0.0]
    moves = [0, 0]
    plies = 0
    while not state.is_terminal():
        if state.is_chance_node():
            rng = random.Random(f"{gseed}:{hist}")
            acts, probs = zip(*state.chance_outcomes(), strict=True)
            a = rng.choices(acts, weights=probs)[0]
        else:
            p = state.current_player()
            slot = slot_of_seat[p]
            t0 = time.perf_counter()
            if slot == 0:
                a = net.act(features(state, p), legal_mask(state), greedy=True)
            else:
                a = opp.choose(state, bot_rng(gseed, hist))
            think[slot] += time.perf_counter() - t0
            moves[slot] += 1
            plies += 1
            if a not in state.legal_actions():
                raise RuntimeError(f"illegal action {a} from slot {slot}")
        state.apply_action(a)
        hist += 1
    returns = state.returns()
    top = max(returns)
    winners = [s for s in range(2) if returns[s] == top]
    credit = 1 / len(winners) if seat_of[0] in winners else 0.0
    return {
        "credit": credit,
        "draw": len(winners) > 1,
        "think": think,
        "moves": moves,
        "plies": plies,
    }


def _play(args: tuple) -> dict:
    return play_one(*args)


def evaluate_policy(
    checkpoint: str, opponent: str, games: int, seed: int, workers: int = 1
) -> dict:
    if opponent == "human" or not is_valid_seat_type(opponent):
        raise ValueError(f"invalid opponent {opponent!r}")
    jobs = [(str(checkpoint), opponent, seed, i) for i in range(games)]
    if workers > 1 and games > 1:
        with Pool(workers) as pool:
            res = pool.map(_play, jobs, chunksize=max(1, games // (workers * 4)))
    else:
        res = [_play(j) for j in jobs]
    wins = sum(r["credit"] for r in res)
    lo, hi = wilson(wins, games)

    def per_move(slot: int) -> float:
        m = sum(r["moves"][slot] for r in res)
        return sum(r["think"][slot] for r in res) / m if m else 0.0

    return {
        "checkpoint": str(checkpoint),
        "opponent": opponent,
        "games": games,
        "seed": seed,
        "wins": wins,
        "win_rate": wins / games if games else 0.0,
        "ci95": [lo, hi],
        "draws": sum(1 for r in res if r["draw"]),
        "policy_mean_move_seconds": per_move(0),
        "opponent_mean_move_seconds": per_move(1),
        "mean_plies": sum(r["plies"] for r in res) / games if games else 0.0,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--checkpoint", type=Path, required=True)
    ap.add_argument("--opponents", nargs="+", required=True)
    ap.add_argument("--games", type=int, default=100)
    ap.add_argument(
        "--games-for", action="append", default=[], metavar="OPP=N", help="per-opponent games"
    )
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--json", type=Path)
    args = ap.parse_args(argv)
    overrides: dict[str, int] = {}
    for item in args.games_for:
        name, _, n = item.rpartition("=")
        if not name or not n.isdigit():
            ap.error(f"bad --games-for {item!r}; expected OPP=N")
        overrides[name] = int(n)
    results = []
    try:
        for opp in args.opponents:
            r = evaluate_policy(
                str(args.checkpoint), opp, overrides.get(opp, args.games), args.seed, args.workers
            )
            results.append(r)
            print(
                f"{opp:<12} games={r['games']:<5} rate={r['win_rate']:.3f} "
                f"CI=[{r['ci95'][0]:.3f}, {r['ci95'][1]:.3f}] "
                f"s/move={r['policy_mean_move_seconds']:.5f} draws={r['draws']}"
            )
    except ValueError as e:
        ap.error(str(e))
    if args.json:
        out = {
            "checkpoint": str(args.checkpoint),
            "greedy": True,
            "tie_convention": TIE_CONVENTION,
            "git_commit": _git_commit(),
            "args": {k: str(v) for k, v in vars(args).items()},
            "results": results,
        }
        args.json.write_text(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
