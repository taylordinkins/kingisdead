# kingisdead

An implementation of *The King is Dead* (Second Edition, Peer Sylvester / Osprey Games) as an
[OpenSpiel](https://github.com/google-deepmind/open_spiel) game, with a FastAPI server, a React web
UI for human play, bots (random, heuristic, MCTS) and a trained AlphaZero policy.

Rules contract: [docs/RULES_SPEC.md](docs/RULES_SPEC.md). Scope, decisions and phases: [PLAN.md](PLAN.md).
**Status:** Phases 0-6 done (2-3 player game, web UI, setup editor, bots, trained policy). 4-player teams and the advanced game are planned.

## Requirements
- Python 3.12-3.14 and [uv](https://docs.astral.sh/uv/)
- Node 20 and npm (for the web UI)
- Optional, for the trained bot and training: PyTorch via `uv sync --group train` (a GPU is only needed for training)

## Run the UI
```bash
uv sync                    # add --group train to play the trained bot
cd web && npm ci

# terminal 1 (repo root): API on :8000
uv run uvicorn server.app:app --port 8000
# terminal 2 (web/): UI on :5173, proxies /api to :8000
npm run dev
```
Open http://localhost:5173. In the lobby pick a seat type per player: Human, Random, Heuristic,
MCTS Easy/Medium/Hard (20/100/400 sims) or **Trained (AlphaZero)**. Click regions and hand cards on
the board to act. The setup editor is at `#/editor`.

## Bots and trained policies
- Seat types are strings: `human`, `random`, `heuristic`, `mcts:N`, `trained:<name>`.
- `trained:<name>` loads `models/<name>.pt` (shipped: `az-2p-v1`) and plays net + MCTS at 50 sims. It
  needs the `train` group and a 2-player game; otherwise game creation returns 422 (CI skips these tests).
- Strength reports: [phase 5 bots](docs/phase-reports/phase-5-bot-strength.md),
  [trained](docs/phase-reports/phase-6-trained-strength.md) (about 0.9 vs heuristic, about 0.8-0.87 vs `mcts:100`).
- Compare bots: `uv run python -m tools.tournament --seats heuristic random --games 100 --seed 0`
- Train a new policy (needs the `train` group): `uv run python -m tools.train_az --out runs/az --minutes 180 --workers 6`,
  evaluate with `uv run python -m tools.eval_policy --checkpoint runs/az/best.pt --opponents heuristic --mode mcts --sims 50`,
  then copy the checkpoint to `models/<name>.pt` to use it as `trained:<name>`.

## Tests and checks
```bash
uv run pytest -q           # fast tests; -m slow for the long simulations
uv run ruff check . && uv run pyright
cd web && npx tsc --noEmit && npm test && npm run e2e   # e2e starts the API and Vite itself
```
The rulebook PDF goes in `docs/rules/` (git-ignored) for the rules-audit agent. `CLAUDE.md` and `.claude/`
hold the Claude Code workflow (agents, `/next-task`, `/close-phase`).

This is an unofficial fan implementation for research; it is not affiliated with Osprey Games.
