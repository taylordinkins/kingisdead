import { createElement } from "react";
import type { GamePlugin } from "../registry";
import Board from "./Board";

export const kingIsDeadPlugin: GamePlugin = {
  id: "king_is_dead",
  title: "The King is Dead",
  renderBoard: (g) => createElement(Board, { game: g }),
};
