import { createElement, type ReactNode } from "react";
import type { GameView, LegalAction } from "../shell/useGame";
import { kingIsDeadPlugin } from "./king-is-dead/plugin";

/** Transient UI state shared between the action list and the board. */
export interface BoardUi {
  /** Id of the legal action currently hovered/focused in the action list. */
  hoverAction: number | null;
  /** True only on a human seat's turn when no request is in flight and no bot is thinking. */
  canAct?: boolean;
  /** Submit a legal action by id (same path as the action list). */
  onAct?: (actionId: number) => void;
}

export interface GamePlugin {
  id: string;
  /** Submit automatically when a human seat has exactly one legal action. */
  autoAdvanceForced?: boolean;
  title: string;
  renderBoard(game: GameView, ui?: BoardUi): ReactNode;
  /** Optional richer label for an action button; must not change the action id. */
  actionLabel?(game: GameView, action: LegalAction): string;
}

export const fallbackPlugin: GamePlugin = {
  id: "generic",
  title: "Game",
  renderBoard: (g) =>
    createElement("pre", { "aria-label": "Game state" }, JSON.stringify(g.view, null, 2)),
};

const plugins: Record<string, GamePlugin> = {
  [kingIsDeadPlugin.id]: kingIsDeadPlugin,
};

export function getPlugin(id: string): GamePlugin {
  return (Object.prototype.hasOwnProperty.call(plugins, id) ? plugins[id] : undefined) ?? fallbackPlugin;
}
