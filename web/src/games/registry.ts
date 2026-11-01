import { createElement, type ReactNode } from "react";
import type { GameView, LegalAction } from "../shell/useGame";
import { kingIsDeadPlugin } from "./king-is-dead/plugin";

/** Transient UI state shared between the action list and the board. */
export interface BoardUi {
  /** Id of the legal action currently hovered/focused in the action list. */
  hoverAction: number | null;
}

export interface GamePlugin {
  id: string;
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
