import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { GameView } from "../../shell/useGame";
import { fallbackPlugin, getPlugin } from "../registry";
import Board from "./Board";
import midgame from "./__fixtures__/midgame.json";
import negotiate from "./__fixtures__/negotiate_disc.json";
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
    const court = screen.getByRole("group", { name: "P0 court" });
    expect(within(court).getByLabelText("3 Scottish")).toBeInTheDocument();
    expect(within(court).getByLabelText("2 English")).toBeInTheDocument();
    const supply = screen.getByRole("group", { name: "Supply" });
    expect(within(supply).getByLabelText("5 Scottish")).toBeInTheDocument();
    expect(within(supply).getByLabelText("0 English")).toBeInTheDocument();
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

describe("negotiate disc placement (playtest 20261031T232657-9588b3)", () => {
  const actions = [
    { id: 8, label: "Region Moray", kind: "region", region: 0, faction: null, card: null },
    { id: 12, label: "Region Gwynedd", kind: "region", region: 4, faction: null, card: null },
  ];
  const g = (over: Partial<GameView> = {}) =>
    game(negotiate, { seats: ["human", "random", "random"], legal_actions: actions, ...over });

  it("shows courts, hands, supply and disc status per seat", () => {
    render(<Board game={g()} />);
    expect(screen.getAllByRole("group", { name: /^Player \d$/ })).toHaveLength(3);
    const court1 = screen.getByRole("group", { name: "P1 court" });
    expect(within(court1).getByLabelText("2 Welsh")).toBeInTheDocument();
    expect(within(court1).getByLabelText("0 Scottish")).toBeInTheDocument();
    const hand1 = screen.getByRole("group", { name: "P1 hand" });
    expect(within(hand1).getByText("Assemble ×2")).toBeInTheDocument();
    expect(within(hand1).getByText("Negotiate")).toBeInTheDocument();
    expect(within(screen.getByRole("group", { name: "P0 hand" })).queryByText("Negotiate")).toBeNull();
    expect(within(screen.getByRole("group", { name: "Supply" })).getByLabelText("7 Welsh")).toBeInTheDocument();
    expect(within(screen.getByRole("group", { name: "P2 negotiation disc" })).getByText("in hand")).toBeInTheDocument();
    expect(screen.getByTestId("player-0")).toHaveAttribute("data-current", "true");
    expect(screen.getByTestId("player-1")).not.toHaveAttribute("data-current");
  });

  it("shows a spent disc with its region and slot number", () => {
    const view = {
      ...negotiate,
      negotiation_discs: [null, 7, null],
      track: negotiate.track.map((t) => (t.slot === 2 ? { ...t, discs: [1] } : t)),
    };
    render(<Board game={g({ view: view as GameView["view"] })} />);
    expect(screen.getByTestId("disc-on-1")).toHaveTextContent("on Devon (slot 3)");
    expect(screen.getByTestId("disc-2-1")).toBeInTheDocument();
  });

  it("numbers slots and highlights legal regions on map and track", () => {
    render(<Board game={g()} />);
    for (let i = 0; i < 8; i++) expect(screen.getByTestId(`slot-number-${i}`)).toHaveTextContent(String(i + 1));
    // Moray is slot 1, Gwynedd slot 7; Devon (slot 3) is not legal.
    expect(screen.getByTestId("slot-badge-0")).toHaveTextContent("1");
    expect(screen.getByTestId("slot-badge-4")).toHaveTextContent("7");
    expect(screen.getByTestId("highlight-0")).toBeInTheDocument();
    expect(screen.getByTestId("highlight-4")).toBeInTheDocument();
    expect(screen.queryByTestId("highlight-7")).toBeNull();
    expect(screen.getByTestId("slot-highlight-0")).toBeInTheDocument();
    expect(screen.getByTestId("slot-highlight-6")).toBeInTheDocument();
    expect(screen.queryByTestId("slot-highlight-2")).toBeNull();
  });

  it("does not highlight when it is not a human turn", () => {
    render(<Board game={g({ seats: ["random", "random", "random"] })} />);
    expect(screen.queryByTestId("highlight-0")).toBeNull();
  });

  it("cross-highlights the region of a hovered action and a hovered slot", () => {
    const { rerender } = render(<Board game={g()} hoverAction={12} />);
    expect(screen.getByTestId("hover-4")).toBeInTheDocument();
    expect(screen.queryByTestId("hover-0")).toBeNull();
    rerender(<Board game={g()} hoverAction={null} />);
    expect(screen.queryByTestId("hover-4")).toBeNull();
    fireEvent.mouseEnter(screen.getByTestId("track-slot-0"));
    expect(screen.getByTestId("hover-0")).toBeInTheDocument();
    fireEvent.mouseLeave(screen.getByTestId("track-slot-0"));
    expect(screen.queryByTestId("hover-0")).toBeNull();
  });

  it("adds the slot number to region action labels without changing ids", () => {
    const p = getPlugin("king_is_dead");
    const game0 = g();
    expect(p.actionLabel?.(game0, actions[0]!)).toBe("Region Moray (slot 1)");
    expect(p.actionLabel?.(game0, actions[1]!)).toBe("Region Gwynedd (slot 7)");
    const other = { id: 3, label: "Pass", kind: "pass" };
    expect(p.actionLabel?.(game0, other)).toBe("Pass");
  });
});
