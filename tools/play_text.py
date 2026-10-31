"""Play one seeded random King is Dead game and print every decision."""

import argparse
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pyspiel  # noqa: E402

import kingisdead.game  # noqa: E402,F401


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--players", type=int, default=2, choices=[2, 3])
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--actions", default="random", choices=["random"])
    args = ap.parse_args()
    rng = random.Random(args.seed)
    game = pyspiel.load_game(f"python_king_is_dead(players={args.players})")
    state = game.new_initial_state()
    step = 0
    while not state.is_terminal():
        if state.is_chance_node():
            outcomes, probs = zip(*state.chance_outcomes(), strict=True)
            a = rng.choices(outcomes, weights=probs)[0]
            print(f"[{step}] chance: {state.action_to_string(state.current_player(), a)}")
        else:
            p = state.current_player()
            legal = state.legal_actions()
            names = ", ".join(f"{x}={state.action_to_string(p, x)}" for x in legal)
            a = rng.choice(legal)
            print(f"[{step}] player {p} legal ({len(legal)}): {names}")
            print(f"[{step}] player {p} chose {a}: {state.action_to_string(p, a)}")
        state.apply_action(a)
        step += 1
    print(state)
    print(f"Final returns: {state.returns()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
