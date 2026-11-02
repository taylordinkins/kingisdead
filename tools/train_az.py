"""AlphaZero-style self-play training (net-guided MCTS; time-boxed, resumable).

Usage: uv run python -m tools.train_az --out runs/az-a --minutes 90 --workers 6 --sims 50
Writes curve.csv, latest.pt, best.pt (best by net+MCTS win rate vs
heuristic over --eval-best-games), state.json, optim.pt to --out.
The replay buffer is not persisted (it refills after --resume).
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main(argv: list[str] | None = None) -> int:
    from kingisdead.rl.az import AZConfig, train

    d = AZConfig()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--minutes", type=float, default=10.0)
    ap.add_argument("--workers", type=int, default=d.workers)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--max-iters", type=int)
    ap.add_argument("--hidden", type=int, nargs="+", default=list(d.hidden_sizes))
    ap.add_argument("--residual", action="store_true")
    ap.add_argument("--sims", type=int, default=d.sims)
    ap.add_argument("--eval-sims", type=int, default=d.eval_sims)
    ap.add_argument("--c-puct", type=float, default=d.c_puct)
    ap.add_argument("--dirichlet-alpha", type=float, default=d.dirichlet_alpha)
    ap.add_argument("--dirichlet-eps", type=float, default=d.dirichlet_eps)
    ap.add_argument("--temp-moves", type=int, default=d.temp_moves)
    ap.add_argument("--games-per-iter", type=int, default=d.games_per_iter)
    ap.add_argument("--buffer-size", type=int, default=d.buffer_size)
    ap.add_argument("--batch-size", type=int, default=d.batch_size)
    ap.add_argument("--sample-reuse", type=float, default=d.sample_reuse)
    ap.add_argument("--min-buffer", type=int, default=d.min_buffer)
    ap.add_argument("--lr", type=float, default=d.lr)
    ap.add_argument("--eval-every", type=int, default=d.eval_every)
    ap.add_argument("--eval-raw-games", type=int, default=d.eval_raw_games)
    ap.add_argument("--eval-mcts-games", type=int, default=d.eval_mcts_games)
    ap.add_argument(
        "--eval-best-games",
        type=int,
        default=d.eval_best_games,
        help="net+MCTS vs heuristic games per eval (picks best.pt), spread over workers",
    )
    a = ap.parse_args(argv)
    cfg = AZConfig(
        hidden_sizes=tuple(a.hidden),
        residual=a.residual,
        workers=a.workers,
        sims=a.sims,
        eval_sims=a.eval_sims,
        c_puct=a.c_puct,
        dirichlet_alpha=a.dirichlet_alpha,
        dirichlet_eps=a.dirichlet_eps,
        temp_moves=a.temp_moves,
        games_per_iter=a.games_per_iter,
        buffer_size=a.buffer_size,
        batch_size=a.batch_size,
        sample_reuse=a.sample_reuse,
        min_buffer=a.min_buffer,
        lr=a.lr,
        eval_every=a.eval_every,
        eval_raw_games=a.eval_raw_games,
        eval_mcts_games=a.eval_mcts_games,
        eval_best_games=a.eval_best_games,
        seed=a.seed,
    )
    run_config = {"cli": vars(a) | {"out": str(a.out)}}
    summary = train(cfg, a.out, a.minutes, a.max_iters, a.resume, run_config=run_config)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
