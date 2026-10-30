# kingisdead

An implementation of *The King is Dead* (Second Edition, Peer Sylvester / Osprey Games) as an
[OpenSpiel](https://github.com/google-deepmind/open_spiel) game, playable by humans in the browser
and usable by OpenSpiel's RL algorithms.

**Status:** Phase 0 (scaffold). See [PLAN.md](PLAN.md) for scope, decisions and phases.

## Quick start

```bash
uv sync
uv run pytest -q
```

Put the rulebook PDF in `docs/rules/` (git-ignored) so the rules-audit agent can read it.

## Working with Claude Code

`CLAUDE.md` and `.claude/` set up the development workflow: Sonnet and Haiku agents do the routine
implementation, Opus agents review. Start a phase with `/start-phase N`; see PLAN.md §8.

This is an unofficial fan implementation for research; it is not affiliated with Osprey Games.
