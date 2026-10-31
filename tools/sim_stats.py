"""Play N seeded random games and report end-type mix and game length."""

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pyspiel  # noqa: E402

import kingisdead.game  # noqa: E402,F401
from kingisdead import constants as C  # noqa: E402

try:
    from tests.support.invariants import InvariantViolation, check_invariants
except ImportError as exc:  # pragma: no cover
    sys.exit(
        f"sim_stats: cannot import tests.support.invariants ({exc}); not reporting 0 violations"
    )


def play(game, rng: random.Random) -> tuple[str, int, int]:
    """Return (end type, decision count, invariant violations)."""
    state = game.new_initial_state()
    decisions = 0
    violations = 0

    def check() -> int:
        try:
            check_invariants(state)
        except InvariantViolation:
            return 1
        return 0

    violations += check()
    while not state.is_terminal():
        if state.is_chance_node():
            outcomes, probs = zip(*state.chance_outcomes(), strict=True)
            state.apply_action(rng.choices(outcomes, weights=probs)[0])
        else:
            state.apply_action(rng.choice(state.legal_actions()))
            decisions += 1
        violations += check()
    # R-400: invasion if the third instability disc is on the board, else coronation.
    unstable = sum(1 for s in state.region_states if s == C.REGION_UNSTABLE)
    end = "invasion" if unstable >= C.INSTABILITY_DISCS else "coronation"
    return end, decisions, violations


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=100)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--players", type=int, choices=[2, 3])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    games = {n: pyspiel.load_game(f"python_king_is_dead(players={n})") for n in (2, 3)}
    rng = random.Random(args.seed)
    ends = {"invasion": 0, "coronation": 0}
    lengths: list[int] = []
    bad = 0
    for i in range(args.games):
        n = args.players or (2, 3)[i % 2]
        end, length, v = play(games[n], rng)
        ends[end] += 1
        lengths.append(length)
        bad += v
    out = {
        "games": args.games,
        "end_types": ends,
        "game_length": {
            "mean": sum(lengths) / len(lengths) if lengths else 0.0,
            "min": min(lengths, default=0),
            "max": max(lengths, default=0),
        },
        "invariant_violations": bad,
    }
    if args.json:
        print(json.dumps(out))
    else:
        print(f"games: {out['games']}")
        for k, v in ends.items():
            print(f"{k}: {v} ({100 * v / max(args.games, 1):.1f}%)")
        gl = out["game_length"]
        print(f"game length (decisions): mean {gl['mean']:.2f} min {gl['min']} max {gl['max']}")
        print(f"invariant violations: {bad}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
