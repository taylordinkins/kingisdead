import { createElement } from "react";
import type { LegalAction } from "../../shell/useGame";
import type { GamePlugin } from "../registry";
import Board from "./Board";
import { playerStyle } from "./board/factions";
import { tryParseKidView } from "./types";

export const kingIsDeadPlugin: GamePlugin = {
  id: "king_is_dead",
  title: "The King is Dead",
  // R-106: only the forced empty-hand PASS is auto-played; other single choices wait for a click
  autoAdvance: (a, legal) => legal.length === 1 && a.kind === "pass",
  renderBoard: (g, ui) => createElement(Board, { game: g, 
      hoverAction: ui?.hoverAction ?? null,
      canAct: ui?.canAct ?? false,
      onAct: ui?.onAct,
      labelFor: (a: LegalAction) => kingIsDeadPlugin.actionLabel?.(g, a) ?? a.label,
    }),
  seatStyle: playerStyle,
  actionLabel: (g, a) => {
    if (a.kind !== "region" || a.region == null) return a.label;
    const v = tryParseKidView(g.view);
    const slot = v?.track.find((t) => t.region === a.region)?.slot;
    return slot === undefined ? a.label : `${a.label} (slot ${slot + 1})`;
  },
};
