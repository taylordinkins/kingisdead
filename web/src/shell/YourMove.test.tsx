import { fireEvent, render, screen, within } from "@testing-library/react";

import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import TabBar, { type ScreenTab } from "./TabBar";
import YourMove from "./YourMove";
import type { LegalAction } from "./useGame";

const act = (id: number, kind: string, label: string): LegalAction =>
  ({ id, kind, label }) as LegalAction;

describe("YourMove", () => {
  it("names the card choice and renders card plays first", () => {
    const onAct = vi.fn();
    render(
      <YourMove
        humanTurn
        waitingFor={null}
        phase="action"
        busy={false}
        onAct={onAct}
        actions={[act(1, "pass", "Pass"), act(2, "play", "Play Assemble"), act(3, "play", "Play Negotiate")]}
      />,
    );
    const panel = screen.getByRole("region", { name: "Your move" });
    expect(within(panel).getByRole("heading")).toHaveTextContent("Your move: choose a card to play");
    expect(panel).toHaveTextContent("Phase: action");
    const buttons = within(panel).getAllByRole("button");
    expect(buttons.map((b) => b.textContent)).toEqual(["Play Assemble", "Play Negotiate", "Pass"]);
    fireEvent.click(buttons[1]!);
    expect(onAct).toHaveBeenCalledWith(3);
  });

  it("asks for an action when there are no card plays", () => {
    render(
      <YourMove humanTurn waitingFor={null} busy={false} onAct={vi.fn()} actions={[act(1, "region", "Moray")]} />,
    );
    expect(screen.getByRole("heading")).toHaveTextContent("Your move: choose an action");
  });

  it("shows a muted waiting state with no buttons when it is not the human's turn", () => {
    render(
      <YourMove humanTurn={false} waitingFor="P1 (random)" busy={false} onAct={vi.fn()} actions={[]} />,
    );
    const panel = screen.getByRole("region", { name: "Your move" });
    expect(panel).toHaveAttribute("data-state", "waiting");
    expect(panel).toHaveTextContent("Waiting for P1 (random)…");
    expect(within(panel).queryAllByRole("button")).toHaveLength(0);
  });
});

describe("TabBar", () => {
  function Harness({ initial = "play" as ScreenTab }) {
    const [t, setT] = useState<ScreenTab>(initial);
    return (
      <>
        <TabBar value={t} onChange={setT} />
        <output>{t}</output>
      </>
    );
  }

  it("offers Play, Board and Log tabs with the current one selected", () => {
    render(<Harness />);
    const tabs = screen.getAllByRole("tab");
    expect(tabs.map((t) => t.textContent)).toEqual(["Play", "Board", "Log"]);
    expect(screen.getByRole("tab", { name: "Play" })).toHaveAttribute("aria-selected", "true");
    fireEvent.click(screen.getByRole("tab", { name: "Log" }));
    expect(screen.getByRole("tab", { name: "Log" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: "Play" })).toHaveAttribute("aria-selected", "false");
    expect(screen.getByRole("status")).toHaveTextContent("log");
  });
});
