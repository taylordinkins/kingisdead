"""Bot-vs-bot tournament: win rates per bot, with Wilson 95% intervals.

Usage: uv run python -m tools.tournament --seats mcts:200 random --games 100 --seed 0

Tie convention: a game's winners are the seats with the maximum return (shared wins).
With k winners each gets 1/k of a win; the game counts once in `draws` when k > 1.
"""

import argparse
import json
import math
import random
import subprocess
import sys
import time
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pyspiel  # noqa: E402

import kingisdead.game  # noqa: E402,F401
from server.bots import bot_rng, get_bot, is_valid_seat_type  # noqa: E402

TIE_CONVENTION = "shared win: k winners (max return) each get 1/k win; game counted in draws if k>1"


def wilson(wins: float, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a proportion (wins may be fractional)."""
    if n <= 0:
        return (0.0, 1.0)
    p = wins / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def game_seed(seed: int, index: int) -> int:
    return random.Random(f"{seed}:game:{index}").getrandbits(62)


def play_game(seats: list[str], seed: int, index: int, rotate: bool) -> dict:
    """Play one game. Bot b sits in seat (b + index) % n when rotating."""
    n = len(seats)
    shift = index % n if rotate else 0
    seat_of_bot = [(b + shift) % n for b in range(n)]
    bot_of_seat = {s: b for b, s in enumerate(seat_of_bot)}
    gseed = game_seed(seed, index)
    game = pyspiel.load_game(f"python_king_is_dead(players={n})")
    state = game.new_initial_state()
    history_len = 0
    plies = 0
    think = [0.0] * n
    moves = [0] * n
    start = time.perf_counter()
    while not state.is_terminal():
        if state.is_chance_node():
            rng = random.Random(f"{gseed}:{history_len}")
            actions, probs = zip(*state.chance_outcomes(), strict=True)
            a = rng.choices(actions, weights=probs)[0]
        else:
            b = bot_of_seat[state.current_player()]
            t0 = time.perf_counter()
            a = get_bot(seats[b]).choose(state, bot_rng(gseed, history_len))
            think[b] += time.perf_counter() - t0
            moves[b] += 1
            if a not in state.legal_actions():
                raise RuntimeError(f"bot {seats[b]!r} chose illegal action {a}")
            plies += 1
        state.apply_action(a)
        history_len += 1
    wall = time.perf_counter() - start
    returns = state.returns()
    top = max(returns)
    winners = [s for s in range(n) if returns[s] == top]
    credit = [0.0] * n
    for s in winners:
        credit[bot_of_seat[s]] += 1 / len(winners)
    return {
        "credit": credit,
        "draw": len(winners) > 1,
        "plies": plies,
        "wall": wall,
        "think": think,
        "moves": moves,
        "seat_of_bot": seat_of_bot,
    }


def _play(args: tuple) -> dict:
    return play_game(*args)


def run_tournament(
    seats: list[str], games: int, seed: int, rotate: bool = True, workers: int = 1
) -> dict:
    n = len(seats)
    if n not in (2, 3):
        raise ValueError("seats must list 2 or 3 bot types")
    for s in seats:
        if s == "human" or not is_valid_seat_type(s):
            raise ValueError(f"invalid bot seat type {s!r}")
    jobs = [(seats, seed, i, rotate) for i in range(games)]
    if workers > 1 and games > 1:
        with Pool(workers) as pool:
            results = pool.map(_play, jobs, chunksize=max(1, games // (workers * 4)))
    else:
        results = [_play(j) for j in jobs]
    wins = [0.0] * n
    think = [0.0] * n
    moves = [0] * n
    seat_counts = [[0] * n for _ in range(n)]  # [bot][seat]
    for r in results:
        for b in range(n):
            wins[b] += r["credit"][b]
            think[b] += r["think"][b]
            moves[b] += r["moves"][b]
            seat_counts[b][r["seat_of_bot"][b]] += 1
    g = len(results)
    bots = []
    for b in range(n):
        lo, hi = wilson(wins[b], g)
        bots.append(
            {
                "slot": b,
                "seat_type": seats[b],
                "wins": wins[b],
                "win_rate": wins[b] / g if g else 0.0,
                "ci95": [lo, hi],
                "mean_move_seconds": think[b] / moves[b] if moves[b] else 0.0,
                "seat_counts": seat_counts[b],
            }
        )
    return {
        "seats": list(seats),
        "games": g,
        "seed": seed,
        "rotate": rotate,
        "tie_convention": TIE_CONVENTION,
        "draws": sum(1 for r in results if r["draw"]),
        "mean_plies": sum(r["plies"] for r in results) / g if g else 0.0,
        "mean_game_seconds": sum(r["wall"] for r in results) / g if g else 0.0,
        "bots": bots,
    }


def _git_commit() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
        )
        return out.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def format_table(res: dict) -> str:
    lines = [f"{'bot':<4}{'type':<12}{'wins':>8}{'rate':>8}{'95% CI':>17}{'s/move':>9}"]
    for b in res["bots"]:
        lo, hi = b["ci95"]
        ci = f"[{lo:.3f}, {hi:.3f}]"
        lines.append(
            f"{b['slot']:<4}{b['seat_type']:<12}{b['wins']:>8.1f}{b['win_rate']:>8.3f}"
            f"{ci:>17}{b['mean_move_seconds']:>9.4f}"
        )
    lines.append(
        f"games={res['games']} draws={res['draws']} mean_plies={res['mean_plies']:.1f} "
        f"mean_game_s={res['mean_game_seconds']:.3f} rotate={res['rotate']}"
    )
    lines.append(f"ties: {res['tie_convention']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seats", nargs="+", required=True, help="bot type per player (2 or 3)")
    ap.add_argument("--games", type=int, default=100)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--rotate", action=argparse.BooleanOptionalAction, default=True)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--json", type=Path, help="write results to this path")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)
    try:
        res = run_tournament(args.seats, args.games, args.seed, args.rotate, args.workers)
    except ValueError as e:
        ap.error(str(e))
    if args.json:
        out = {**res, "args": {k: str(v) for k, v in vars(args).items()}}
        out["git_commit"] = _git_commit()
        args.json.write_text(json.dumps(out, indent=2))
    if not args.quiet:
        print(format_table(res))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
