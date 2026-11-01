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
  onAct?: (actionId: number) => void | Promise<unknown>;
}

export interface GamePlugin {
  id: string;
  /** Whether the sole legal action on a human turn should be submitted automatically. */
  autoAdvance?(action: LegalAction, legalActions: LegalAction[]): boolean;
  title: string;
  renderBoard(game: GameView, ui?: BoardUi): ReactNode;
  /** Optional map-only half of the board; with renderSide it replaces renderBoard in the shell. */
  renderMain?(game: GameView, ui?: BoardUi): ReactNode;
  /** Optional right-column content under the "Your move" panel (status, seats, results). */
  renderSide?(game: GameView, ui?: BoardUi): ReactNode;
  /** Optional short phase name shown in the "Your move" panel. */
  phaseLabel?(game: GameView): string | undefined;
  /** Optional seat colours for the action log. */
  seatStyle?(seat: number): { fill: string; ink: string };
  /** Optional richer label for an action button; must not change the action id. */
  actionLabel?(game: GameView, action: LegalAction): string;
  /** Optional tooltip text for an action button. */
  actionHelp?(game: GameView, action: LegalAction): string | undefined;
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
