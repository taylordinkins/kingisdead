import { useState, type ReactNode } from "react";
import { api } from "../api/client";
import ActionList from "./ActionList";
import ActionLog from "./ActionLog";
import ImportButton from "./ImportButton";
import { getPlugin, type BoardUi } from "../games/registry";
import ReportDialog from "./ReportDialog";
import {
  errorText,
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
  /** Slot for the game-specific board (unit 9); overrides the registry plugin. */
  renderBoard?: (game: GameView, ui?: BoardUi) => ReactNode;
  onExit?: () => void;
  /** Called with the new game id after a replay import. */
  onImported?: (gameId: string) => void;
}

async function downloadExport(gameId: string): Promise<void> {
  const { data, error } = await api.GET("/api/games/{game_id}/export", {
    params: { path: { game_id: gameId } },
  });
  if (!data) throw new Error(errorText(error));
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }),
  );
  const a = document.createElement("a");
  a.href = url;
  a.download = `kid-${gameId}.json`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export default function GameScreen({
  gameId,
  pollMs = DEFAULT_POLL,
  renderBoard,
  onExit,
  onImported,
}: Props) {
  const [gameName, setGameName] = useState("");
  const { game, error, busy, act, goBack, rewind, botThinking, autoNote } = useGame(
    gameId,
    pollMs,
    { autoAdvance: getPlugin(gameName).autoAdvance },
  );
  if (game && game.game !== gameName) setGameName(game.game);
  const [hoverAction, setHoverAction] = useState<number | null>(null);
  const [reporting, setReporting] = useState(false);
  const [rewindTo, setRewindTo] = useState("0");
  const [exportError, setExportError] = useState<string | null>(null);
  const rewindValid = /^\d+$/.test(rewindTo.trim());
  const plugin = getPlugin(game?.game ?? "");
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
          {autoNote && !over && <p role="status">{autoNote} (only legal action)</p>}
          {over ? (
            <div aria-label="Game over">
              <h2>Game over</h2>
              {game.winners && (
                <p>Winner(s): {game.winners.map((p) => `P${p}`).join(", ")}</p>
              )}
              {game.returns && (
                <p>Scores: {game.returns.join(", ")}</p>
              )}
            </div>
          ) : (
            cp !== null && (
              <p>
                Current player: P{cp} ({game.seats[cp]})
              </p>
            )
          )}
          <div role="toolbar" aria-label="Game tools">
            <button
              type="button"
              disabled={busy || game.history_length === 0}
              onClick={() => void goBack()}
            >
              Back
            </button>{" "}
            {game.dev_mode && (
              <span>
                <label>
                  Rewind to player action{" "}
                  <input
                    value={rewindTo}
                    onChange={(e) => setRewindTo(e.target.value)}
                    inputMode="numeric"
                  />
                </label>{" "}
                <button
                  type="button"
                  disabled={busy || !rewindValid}
                  onClick={() => void rewind(Number(rewindTo.trim()))}
                >
                  Rewind
                </button>{" "}
              </span>
            )}
            <button
              type="button"
              onClick={() => {
                setExportError(null);
                downloadExport(gameId).catch((e: unknown) =>
                  setExportError(e instanceof Error ? e.message : "Export failed"),
                );
              }}
            >
              Export replay
            </button>{" "}
            {onImported && <ImportButton onImported={onImported} />}{" "}
            <button type="button" onClick={() => setReporting(true)}>
              Report a problem
            </button>
            {exportError && <p role="alert">Export error: {exportError}</p>}
          </div>
          {reporting && <ReportDialog gameId={gameId} onClose={() => setReporting(false)} />}
          {(renderBoard ?? getPlugin(game.game).renderBoard)(game, {
            hoverAction,
            canAct: !over && humanTurn && !busy,
            onAct: (id) => void act(id),
          })}
          <h3>Action log</h3>
          <ActionLog history={game.history} />
          {!over && humanTurn && (
            <ActionList
              actions={legalActions(game)}
              disabled={busy}
              onAct={(id) => void act(id)}
              labelFor={(a) => plugin.actionLabel?.(game, a) ?? a.label}
              onHover={setHoverAction}
            />
          )}
        </>
      )}
    </section>
  );
}
