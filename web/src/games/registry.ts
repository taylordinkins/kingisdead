import { createElement, type ReactNode } from "react";
import type { GameView } from "../shell/useGame";
import { kingIsDeadPlugin } from "./king-is-dead/plugin";

export interface GamePlugin {
  id: string;
  title: string;
  renderBoard(game: GameView): ReactNode;
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
