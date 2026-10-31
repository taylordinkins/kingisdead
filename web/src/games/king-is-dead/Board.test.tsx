import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { GameView } from "../../shell/useGame";
import { fallbackPlugin, getPlugin } from "../registry";
import Board from "./Board";
import midgame from "./__fixtures__/midgame.json";
import terminal from "./__fixtures__/terminal.json";

function game(view: unknown, over: Partial<GameView> = {}): GameView {
  return {
    id: "g1",
    game: "king_is_dead",
    seats: ["human", "random"],
    seat_types: ["human", "random"],
    seed: 1,
    bot_thinking: false,
    seat: 0,
    history_length: 0,
    history: [],
    dev_mode: false,
    current_player: 0,
    is_terminal: false,
    legal_actions: [],
    view: view as GameView["view"],
    ...over,
  };
}

describe("King is Dead board", () => {
  it("renders a mid-game view", () => {
    render(<Board game={game(midgame)} />);
    const status = screen.getByLabelText("Turn status");
    expect(within(status).getByText("Current player").nextSibling).toHaveTextContent("P1");
    const regions = screen.getByRole("table", { name: "Regions" });
    expect(within(regions).getByRole("row", { name: /Moray/ })).toBeInTheDocument();
    expect(within(regions).getAllByRole("row")).toHaveLength(9);
    expect(screen.getByRole("table", { name: "Region track" })).toBeInTheDocument();
    const courts = screen.getByRole("table", { name: "Courts" });
    expect(within(courts).getByRole("row", { name: /P0 court 3 0 2/ })).toBeInTheDocument();
    expect(within(courts).getByRole("row", { name: /Supply 5 2 0/ })).toBeInTheDocument();
    expect(screen.queryByLabelText("Result")).toBeNull();
  });

  it("renders result and scoring breakdown when terminal", () => {
    render(<Board game={game(terminal, { is_terminal: true })} />);
    const result = screen.getByLabelText("Result");
    expect(within(result).getByText(/Winner\(s\): P1/)).toBeInTheDocument();
    expect(within(result).getByRole("table", { name: "Scores" })).toBeInTheDocument();
    expect(within(result).getByRole("table", { name: "Scoring steps" })).toBeInTheDocument();
    expect(within(result).getByText(/rank 1 followers/)).toBeInTheDocument();
  });

  it("shows names from the view and a progress line", () => {
    render(<Board game={game(midgame)} />);
    const regions = screen.getByRole("table", { name: "Regions" });
    for (const f of midgame.faction_names) {
      expect(within(regions).getByRole("columnheader", { name: f })).toBeInTheDocument();
    }
    expect(screen.getByText("Regions resolved: 0 of 8")).toBeInTheDocument();
  });

  it("uses names from the view, not built-in copies", () => {
    const view = { ...midgame, faction_names: ["Aa", "Bb", "Cc"] };
    render(<Board game={game(view)} />);
    expect(screen.getAllByRole("columnheader", { name: "Bb" })[0]).toBeInTheDocument();
  });

  it("rejects a view without names", () => {
    const { faction_names: _f, ...rest } = midgame;
    render(<Board game={game(rest)} />);
    expect(screen.getByRole("alert")).toHaveTextContent(/faction_names/);
  });

  it("shows the recent-win legend and readable values", () => {
    render(<Board game={game(terminal, { is_terminal: true })} />);
    const result = screen.getByLabelText("Result");
    expect(within(result).getByText(/most recently took control/)).toBeInTheDocument();
    expect(within(result).getByText(/Recent win:.*(struggle \d|never)/)).toBeInTheDocument();
  });

  it("shows a readable error for a malformed view", () => {
    render(<Board game={game({ regions: "nope" })} />);
    expect(screen.getByRole("alert")).toHaveTextContent(/Cannot display board.*King is Dead view/);
  });

  it("shows an error for an empty view", () => {
    render(<Board game={game({})} />);
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });
});

describe("registry", () => {
  it("returns the King is Dead plugin", () => {
    expect(getPlugin("king_is_dead").title).toBe("The King is Dead");
  });
  it("falls back to a JSON dump for unknown games", () => {
    const p = getPlugin("nope");
    expect(p).toBe(fallbackPlugin);
    expect(getPlugin("constructor")).toBe(fallbackPlugin);
    render(<>{p.renderBoard(game({ a: 1 }, { game: "nope" }))}</>);
    expect(screen.getByLabelText("Game state")).toHaveTextContent('"a": 1');
  });
});
