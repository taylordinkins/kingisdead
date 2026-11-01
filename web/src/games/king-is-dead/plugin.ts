import { createElement } from "react";
import type { LegalAction } from "../../shell/useGame";
import type { GamePlugin } from "../registry";
import Board from "./Board";
import { tryParseKidView } from "./types";

export const kingIsDeadPlugin: GamePlugin = {
  id: "king_is_dead",
  title: "The King is Dead",
  autoAdvanceForced: true, // R-106: empty-hand PASS is submitted automatically
  renderBoard: (g, ui) => createElement(Board, { game: g, 
      hoverAction: ui?.hoverAction ?? null,
      canAct: ui?.canAct ?? false,
      onAct: ui?.onAct,
      labelFor: (a: LegalAction) => kingIsDeadPlugin.actionLabel?.(g, a) ?? a.label,
    }),
  actionLabel: (g, a) => {
    if (a.kind !== "region" || a.region == null) return a.label;
    const v = tryParseKidView(g.view);
    const slot = v?.track.find((t) => t.region === a.region)?.slot;
    return slot === undefined ? a.label : `${a.label} (slot ${slot + 1})`;
  },
};
