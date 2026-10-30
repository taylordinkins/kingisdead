---
paths:
  - "server/**"
  - "web/**"
---

# Server and web conventions

- The server owns game state; the action history is the single source of truth and state is rebuilt
  by replaying it. The frontend never decides legality: it renders the server's legal-action list.
- Keep the shell game-agnostic. King-is-Dead specifics live only in the server adapter and
  `web/src/games/king-is-dead/`.
- TypeScript is strict. API types are generated from FastAPI's OpenAPI schema; don't hand-write them.
- Draw our own schematic map. Never reproduce the published board, card or box art.
- Every playable change keeps the Playwright smoke test (full game vs random bot) passing.
