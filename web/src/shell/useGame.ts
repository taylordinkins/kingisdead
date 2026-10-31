import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { components } from "../api/schema";

export type GameView = components["schemas"]["GameView"];
export type SeatType = components["schemas"]["GameView"]["seats"][number];

export interface LegalAction {
  id: number;
  label: string;
  [key: string]: unknown;
}

export interface PollIntervals {
  /** ms between polls while a bot is acting or it is not a human seat's turn. */
  fast: number;
  /** ms between polls otherwise (waiting on a human). */
  slow: number;
}

export const DEFAULT_POLL: PollIntervals = { fast: 500, slow: 2000 };

/** Generic fields the shell reads from the adapter-defined `view` payload. */
export function legalActions(g: GameView): LegalAction[] {
  const v = g.view["legal_actions"];
  return Array.isArray(v) ? (v as LegalAction[]) : [];
}

export function isTerminal(g: GameView): boolean {
  return g.view["is_terminal"] === true;
}

export function currentPlayer(g: GameView): number | null {
  const c = g.view["current_player"];
  return typeof c === "number" ? c : null;
}

function errorText(error: unknown): string {
  if (error && typeof error === "object") {
    const detail = (error as { detail?: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (detail !== undefined) return JSON.stringify(detail);
  }
  return typeof error === "string" ? error : "Request failed";
}

export function useGame(gameId: string, poll: PollIntervals = DEFAULT_POLL) {
  const [game, setGame] = useState<GameView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);
  const alive = useRef(true);

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  const refresh = useCallback(async () => {
    if (busyRef.current) return;
    try {
      const { data, error: err } = await api.GET("/api/games/{game_id}", {
        params: { path: { game_id: gameId } },
      });
      if (!alive.current || busyRef.current) return;
      if (data) {
        setGame(data);
        setError(null);
      } else {
        setError(errorText(err));
      }
    } catch (e) {
      if (alive.current) setError(e instanceof Error ? e.message : "Network error");
    }
  }, [gameId]);

  const act = useCallback(
    async (action: number) => {
      if (busyRef.current) return;
      busyRef.current = true;
      setBusy(true);
      try {
        const { data, error: err } = await api.POST("/api/games/{game_id}/actions", {
          params: { path: { game_id: gameId } },
          body: { action },
        });
        if (!alive.current) return;
        if (data) {
          setGame(data);
          setError(null);
        } else {
          setError(errorText(err));
        }
      } catch (e) {
        if (alive.current) setError(e instanceof Error ? e.message : "Network error");
      } finally {
        busyRef.current = false;
        if (alive.current) setBusy(false);
      }
    },
    [gameId],
  );

  // Initial load (and reload when the game id changes).
  useEffect(() => {
    setGame(null);
    setError(null);
    void refresh();
  }, [refresh]);

  const done = game !== null && isTerminal(game);
  let botActive = false;
  if (game !== null) {
    const cp = currentPlayer(game);
    botActive = game.bot_thinking || (cp !== null && game.seats[cp] !== "human");
  }
  const interval = botActive ? poll.fast : poll.slow;

  // Poll; re-armed after each completed request so it never overlaps itself.
  // `error` is a dependency so polling keeps going after a failed poll.
  useEffect(() => {
    if (game === null || done) return;
    const t = setTimeout(() => void refresh(), interval);
    return () => clearTimeout(t);
  }, [game, done, interval, refresh, error]);

  return { game, error, busy, act, refresh, botThinking: !!game?.bot_thinking && !done };
}
