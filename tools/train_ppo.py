"""Self-play PPO training (time-boxed, resumable).

Usage: uv run python -m tools.train_ppo --out runs/ppo-a --minutes 90 --workers 6 --seed 0
Writes curve.csv, latest.pt, best.pt (best vs heuristic), state.json, optim.pt to --out.
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main(argv: list[str] | None = None) -> int:
    from kingisdead.rl.ppo import PPOConfig, train

    d = PPOConfig()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--minutes", type=float, default=10.0)
    ap.add_argument("--workers", type=int, default=d.workers)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--players", type=int, default=2)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--max-updates", type=int)
    ap.add_argument("--hidden", type=int, nargs="+", default=list(d.hidden_sizes))
    ap.add_argument("--residual", action="store_true")
    ap.add_argument("--games-per-update", type=int, default=d.games_per_update)
    ap.add_argument("--epochs", type=int, default=d.epochs)
    ap.add_argument("--minibatch", type=int, default=d.minibatch)
    ap.add_argument("--lr", type=float, default=d.lr)
    ap.add_argument("--ent-coef", type=float, default=d.ent_coef)
    ap.add_argument("--opponent-frac", type=float, default=d.opponent_frac)
    ap.add_argument("--eval-every", type=int, default=d.eval_every)
    ap.add_argument("--eval-games", type=int, default=d.eval_games)
    ap.add_argument("--snapshot-every", type=int, default=d.snapshot_every)
    a = ap.parse_args(argv)
    cfg = PPOConfig(
        num_players=a.players,
        hidden_sizes=tuple(a.hidden),
        residual=a.residual,
        workers=a.workers,
        games_per_update=a.games_per_update,
        epochs=a.epochs,
        minibatch=a.minibatch,
        lr=a.lr,
        ent_coef=a.ent_coef,
        opponent_frac=a.opponent_frac,
        eval_every=a.eval_every,
        eval_games=a.eval_games,
        snapshot_every=a.snapshot_every,
        seed=a.seed,
    )
    summary = train(cfg, a.out, a.minutes, a.max_updates, a.resume)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
