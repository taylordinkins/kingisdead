import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { GameView, LegalAction } from "../../shell/useGame";
import { getPlugin } from "../registry";
import midgame from "./__fixtures__/midgame.json";

const act = (a: Partial<LegalAction> & { id: number; label: string; kind: string }): LegalAction =>
  ({ region: null, faction: null, card: null, ...a }) as LegalAction;

const ACTIONS: LegalAction[] = [
  act({ id: 0, label: "Pass", kind: "pass" }),
  act({ id: 4, label: "Play Assemble", kind: "play", card: 4 }),
  act({ id: 20, label: "English follower in Lancaster", kind: "follower", region: 2, faction: 2 }),
  act({ id: 19, label: "Scottish follower in Lancaster", kind: "follower", region: 2, faction: 0 }),
  act({ id: 23, label: "English follower in Devon", kind: "follower", region: 7, faction: 2 }),
];

function game(over: Partial<GameView> = {}): GameView {
  return {
    id: "g1",
    game: "king_is_dead",
    seats: ["random", "human"],
    seat_types: ["random", "human"],
    seed: 1,
    bot_thinking: false,
    seat: 1,
    history_length: 0,
    history: [],
    dev_mode: false,
    current_player: 1,
    is_terminal: false,
    legal_actions: ACTIONS,
    view: midgame as unknown as GameView["view"],
    ...over,
  };
}

function setup(over: Partial<GameView> = {}, canAct = true) {
  const onAct = vi.fn();
  const g = game(over);
  const p = getPlugin("king_is_dead");
  render(<>{p.renderBoard(g, { hoverAction: null, canAct, onAct })}</>);
  return onAct;
}

describe("click-to-act", () => {
  it("submits the single action targeting a clicked region", () => {
    const onAct = setup();
    fireEvent.click(screen.getByTestId("region-7"));
    expect(onAct).toHaveBeenCalledTimes(1);
    expect(onAct).toHaveBeenCalledWith(23);
    expect(screen.getByTestId("region-7")).toHaveAttribute("aria-label", expect.stringMatching(/^English follower in Devon\./));
  });

  it("leaves regions without legal actions inert", () => {
    const onAct = setup();
    const r = screen.getByTestId("region-0");
    expect(r).toHaveAttribute("role", "group");
    fireEvent.click(r);
    expect(onAct).not.toHaveBeenCalled();
  });

  it("offers a faction chooser when several actions target one region", () => {
    const onAct = setup();
    fireEvent.click(screen.getByTestId("region-2"));
    expect(onAct).not.toHaveBeenCalled();
    const chooser = screen.getByTestId("region-chooser");
    const buttons = within(chooser).getAllByRole("button", { name: /follower in Lancaster/ });
    expect(buttons).toHaveLength(2);
    expect(buttons[0]).toHaveStyle({ background: "rgb(213, 94, 0)" });
    fireEvent.click(within(chooser).getByRole("button", { name: "Scottish follower in Lancaster" }));
    expect(onAct).toHaveBeenCalledTimes(1);
    expect(onAct).toHaveBeenCalledWith(19);
    expect(screen.queryByTestId("region-chooser")).toBeNull();
  });

  it("closes the chooser with Cancel", () => {
    setup();
    fireEvent.click(screen.getByTestId("region-2"));
    fireEvent.click(screen.getByRole("button", { name: "Cancel choice" }));
    expect(screen.queryByTestId("region-chooser")).toBeNull();
  });

  it("plays a card by clicking it in the current player's hand", () => {
    const onAct = setup();
    const hand = screen.getByRole("group", { name: "P1 hand" });
    fireEvent.click(within(hand).getByRole("button", { name: "Play Assemble" }));
    expect(onAct).toHaveBeenCalledTimes(1);
    expect(onAct).toHaveBeenCalledWith(4);
    // Other players' hands are never clickable.
    expect(within(screen.getByRole("group", { name: "P0 hand" })).queryByRole("button")).toBeNull();
  });

  it("activates with Enter and Space on the keyboard", () => {
    const onAct = setup();
    const r = screen.getByTestId("region-7");
    expect(r).toHaveAttribute("tabindex", "0");
    expect(r).toHaveAttribute("role", "button");
    fireEvent.keyDown(r, { key: "Enter" });
    fireEvent.keyDown(r, { key: " " });
    expect(onAct).toHaveBeenNthCalledWith(1, 23);
    expect(onAct).toHaveBeenNthCalledWith(2, 23);
  });

  it("cross-highlights on hover of a clickable region", () => {
    setup();
    fireEvent.mouseEnter(screen.getByTestId("region-7"));
    expect(screen.getByTestId("hover-7")).toBeInTheDocument();
  });

  it.each([
    ["not a human seat", { seats: ["random", "random"] }, true],
    ["a bot is thinking / busy (canAct false)", {}, false],
    ["game over", { is_terminal: true }, true],
  ])("does nothing when %s", (_n, over, canAct) => {
    const onAct = setup(over as Partial<GameView>, canAct);
    const r = screen.getByTestId("region-7");
    expect(r).toHaveAttribute("role", "group");
    fireEvent.click(r);
    fireEvent.keyDown(r, { key: "Enter" });
    expect(onAct).not.toHaveBeenCalled();
    expect(within(screen.getByRole("group", { name: "P1 hand" })).queryByRole("button")).toBeNull();
  });
});
