import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { components } from "../api/schema";

export type GameView = components["schemas"]["GameView"];
export type SeatType = components["schemas"]["GameView"]["seats"][number];

export type LegalAction = components["schemas"]["LegalAction"];

export interface PollIntervals {
  /** ms between polls while a bot is acting or it is not a human seat's turn. */
  fast: number;
  /** ms between polls otherwise (waiting on a human). */
  slow: number;
}

export const DEFAULT_POLL: PollIntervals = { fast: 500, slow: 2000 };

export const legalActions = (g: GameView): LegalAction[] => g.legal_actions;
export const isTerminal = (g: GameView): boolean => g.is_terminal;
export const currentPlayer = (g: GameView): number | null => g.current_player;

export function errorText(error: unknown): string {
  if (error && typeof error === "object") {
    const detail = (error as { detail?: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (detail !== undefined) return JSON.stringify(detail);
  }
  return typeof error === "string" ? error : "Request failed";
}

export interface GameOptions {
  /** Auto-submit the sole legal action on a human turn when this returns true. */
  autoAdvance?: (action: LegalAction, legal: LegalAction[]) => boolean;
  /** ms to wait before auto-submitting (default 300). */
  autoAdvanceDelay?: number;
}

export function useGame(
  gameId: string,
  poll: PollIntervals = DEFAULT_POLL,
  options: GameOptions = {},
) {
  const { autoAdvance, autoAdvanceDelay = 300 } = options;
  const [game, setGame] = useState<GameView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [pollTick, setPollTick] = useState(0);
  const [autoNote, setAutoNote] = useState<string | null>(null);
  const busyRef = useRef(false);
  const alive = useRef(true);
  /** Bumped on every local mutation; poll responses started earlier are dropped. */
  const mutation = useRef(0);
  const lastAuto = useRef<string | null>(null);

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  const refresh = useCallback(async () => {
    if (busyRef.current) return;
    const started = mutation.current;
    try {
      const { data, error: err } = await api.GET("/api/games/{game_id}", {
        params: { path: { game_id: gameId } },
      });
      if (!alive.current || busyRef.current || mutation.current !== started) return;
      if (data) {
        setGame(data);
        setError(null);
      } else {
        setError(errorText(err));
      }
    } catch (e) {
      if (alive.current && mutation.current === started)
        setError(e instanceof Error ? e.message : "Network error");
    } finally {
      // Re-arm polling even when state/error did not change (identical errors).
      if (alive.current) setPollTick((n) => n + 1);
    }
  }, [gameId]);

  const run = useCallback(async (call: () => Promise<{ data?: GameView; error?: unknown }>) => {
    if (busyRef.current) return;
    busyRef.current = true;
    mutation.current += 1;
    setBusy(true);
    try {
      const { data, error: err } = await call();
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
      mutation.current += 1;
      busyRef.current = false;
      if (alive.current) setBusy(false);
    }
  }, []);

  const act = useCallback(
    (action: number) =>
      run(() =>
        api.POST("/api/games/{game_id}/actions", {
          params: { path: { game_id: gameId } },
          body: { action },
        }),
      ),
    [gameId, run],
  );

  const goBack = useCallback(
    () =>
      run(() => api.POST("/api/games/{game_id}/back", { params: { path: { game_id: gameId } } })),
    [gameId, run],
  );

  const rewind = useCallback(
    (playerActions: number) =>
      run(() =>
        api.POST("/api/games/{game_id}/rewind", {
          params: { path: { game_id: gameId } },
          body: { player_actions: playerActions },
        }),
      ),
    [gameId, run],
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
  }, [game, done, interval, refresh, error, pollTick]);

  // Forced-move auto-advance: one legal action on a human seat's turn.
  useEffect(() => {
    if (!autoAdvance || game === null || done || busy) return;
    const cp = currentPlayer(game);
    if (cp === null || game.seats[cp] !== "human" || game.bot_thinking) return;
    const legal = legalActions(game);
    if (legal.length !== 1) return;
    const only = legal[0]!;
    if (!autoAdvance(only, legal)) return;
    const key = `${game.id}:${game.history_length}:${only.id}`;
    if (lastAuto.current === key) return; // already tried for this state; no loops
    const t = setTimeout(() => {
      lastAuto.current = key;
      setAutoNote(`Auto-played: ${only.label}`);
      void act(only.id);
    }, autoAdvanceDelay);
    return () => clearTimeout(t);
  }, [game, done, busy, autoAdvance, autoAdvanceDelay, act]);

  return {
    game,
    error,
    busy,
    act,
    goBack,
    rewind,
    refresh,
    autoNote,
    botThinking: !!game?.bot_thinking && !done,
  };
}
