import { useState, type ReactNode } from "react";
import "./layout.css";
import { api } from "../api/client";
import ActionLog from "./ActionLog";
import ImportButton from "./ImportButton";
import { getPlugin, type BoardUi } from "../games/registry";
import ReportDialog from "./ReportDialog";
import TabBar, { type ScreenTab } from "./TabBar";
import YourMove from "./YourMove";
import { thinkingText } from "./seatTypes";
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
  const { game, error, busy, act, goBack, rewind, refresh, botThinking, autoNote } = useGame(
    gameId,
    pollMs,
    { autoAdvance: getPlugin(gameName).autoAdvance },
  );
  if (game && game.game !== gameName) setGameName(game.game);
  const [tab, setTab] = useState<ScreenTab>("play");
  const [hoverAction, setHoverAction] = useState<number | null>(null);
  const [reporting, setReporting] = useState(false);
  const [rewindTo, setRewindTo] = useState("0");
  const [exportError, setExportError] = useState<string | null>(null);
  const rewindValid = /^\d+$/.test(rewindTo.trim());
  const plugin = getPlugin(game?.game ?? "");
  const over = game !== null && isTerminal(game);
  const cp = game ? currentPlayer(game) : null;
  const humanTurn = game !== null && cp !== null && game.seats[cp] === "human" && !game.bot_thinking;

  const split = !renderBoard && !!plugin.renderMain && !!plugin.renderSide;
  const phase = game ? plugin.phaseLabel?.(game) : undefined;
  const ui: BoardUi | undefined = game
    ? {
        hoverAction,
        canAct: !over && humanTurn && !busy,
        onAct: (id) => act(id),
      }
    : undefined;

  return (
    <section className="kid-screen" data-tab={tab}>
      <div className="kid-topbar">
        {onExit && (
          <button type="button" onClick={onExit}>
            Lobby
          </button>
        )}
        {game && (
          <p className="kid-status-line">
            Game {game.id} · seats: {game.seats.join(", ")} · seed {game.seed}
          </p>
        )}
        {game && (
          <div role="toolbar" aria-label="Game tools">
            <button
              type="button"
              disabled={busy || game.history_length === 0}
              onClick={() => void goBack()}
            >
              Back
            </button>
            {game.dev_mode && (
              <span>
                <label>
                  Rewind to player action{" "}
                  <input
                    value={rewindTo}
                    onChange={(e) => setRewindTo(e.target.value)}
                    inputMode="numeric"
                    size={4}
                  />
                </label>{" "}
                <button
                  type="button"
                  disabled={busy || !rewindValid}
                  onClick={() => void rewind(Number(rewindTo.trim()))}
                >
                  Rewind
                </button>
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
            </button>
            {onImported && <ImportButton onImported={onImported} />}
            <button type="button" onClick={() => setReporting(true)}>
              Report a problem
            </button>
          </div>
        )}
      </div>
      {exportError && <p role="alert">Export error: {exportError}</p>}
      {error && <p role="alert">Error: {error}</p>}
      {!game && !error && <p>Loading…</p>}
      {game && ui && (
        <>
          {reporting && <ReportDialog gameId={gameId} onClose={() => setReporting(false)} />}
          <TabBar value={tab} onChange={setTab} />
          <div className="kid-grid">
            <div className="kid-pane-board">
              {split ? plugin.renderMain?.(game, ui) : (renderBoard ?? plugin.renderBoard)(game, ui)}
            </div>
            <div className="kid-side">
              <div className="kid-pane-play">
                {botThinking && cp !== null && (
                  <p role="status">{thinkingText(game.seats[cp] ?? "", cp)}</p>
                )}
                {game.bot_error && !over && (
                  <div role="alert">
                    Bot error: {game.bot_error}{" "}
                    <button
                      type="button"
                      onClick={() =>
                        void api
                          .POST("/api/games/{game_id}/bots/retry", {
                            params: { path: { game_id: gameId } },
                          })
                          .then(() => refresh())
                      }
                    >
                      Retry
                    </button>
                  </div>
                )}
                {autoNote && !over && <p role="status">{autoNote} (only legal action)</p>}
                {over ? (
                  <div aria-label="Game over">
                    <h2>Game over</h2>
                    {game.winners && <p>Winner(s): {game.winners.map((p) => `P${p}`).join(", ")}</p>}
                    {game.returns && <p>Scores: {game.returns.join(", ")}</p>}
                  </div>
                ) : (
                  cp !== null && (
                    <>
                      <YourMove
                        humanTurn={humanTurn}
                        waitingFor={`P${cp} (${game.seats[cp]})`}
                        phase={phase}
                        actions={legalActions(game)}
                        busy={busy}
                        onAct={(id) => void act(id)}
                        labelFor={(a) => plugin.actionLabel?.(game, a) ?? a.label}
                        onHover={setHoverAction}
                      />
                      <p>
                        Current player: P{cp} ({game.seats[cp]})
                      </p>
                    </>
                  )
                )}
                {split && plugin.renderSide?.(game, ui)}
              </div>
              <div className="kid-log kid-pane-log">
                <h3>Action log</h3>
                <ActionLog history={game.history} actorStyle={plugin.seatStyle} />
              </div>
            </div>
          </div>
        </>
      )}
    </section>
  );
}
