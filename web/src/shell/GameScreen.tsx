import type { ReactNode } from "react";
import ActionList from "./ActionList";
import {
  currentPlayer,
  DEFAULT_POLL,
  isTerminal,
  legalActions,
  useGame,
  type GameView,
  type PollIntervals,
} from "./useGame";

interface Props {
  gameId: string;
  pollMs?: PollIntervals;
  /** Slot for the game-specific board (unit 9); defaults to a JSON dump. */
  renderBoard?: (game: GameView) => ReactNode;
  onExit?: () => void;
}

const defaultBoard = (g: GameView): ReactNode => (
  <pre aria-label="Game state">{JSON.stringify(g.view, null, 2)}</pre>
);

export default function GameScreen({
  gameId,
  pollMs = DEFAULT_POLL,
  renderBoard = defaultBoard,
  onExit,
}: Props) {
  const { game, error, busy, act, botThinking } = useGame(gameId, pollMs);
  const over = game !== null && isTerminal(game);
  const cp = game ? currentPlayer(game) : null;
  const humanTurn = game !== null && cp !== null && game.seats[cp] === "human" && !game.bot_thinking;

  return (
    <section>
      {onExit && (
        <button type="button" onClick={onExit}>
          Lobby
        </button>
      )}
      {error && <p role="alert">Error: {error}</p>}
      {!game && !error && <p>Loading…</p>}
      {game && (
        <>
          <p>
            Game {game.id} · seats: {game.seats.join(", ")} · seed {game.seed}
          </p>
          {botThinking && <p role="status">Bot is thinking…</p>}
          {over ? (
            <div aria-label="Game over">
              <h2>Game over</h2>
              {Array.isArray(game.view["winners"]) && (
                <p>Winner(s): {(game.view["winners"] as number[]).map((p) => `P${p}`).join(", ")}</p>
              )}
              {Array.isArray(game.view["returns"]) && (
                <p>Scores: {(game.view["returns"] as number[]).join(", ")}</p>
              )}
            </div>
          ) : (
            cp !== null && (
              <p>
                Current player: P{cp} ({game.seats[cp]})
              </p>
            )
          )}
          {renderBoard(game)}
          {!over && humanTurn && (
            <ActionList actions={legalActions(game)} disabled={busy} onAct={(id) => void act(id)} />
          )}
        </>
      )}
    </section>
  );
}
