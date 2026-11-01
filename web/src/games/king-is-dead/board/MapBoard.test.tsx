import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { KidView } from "../types";
import { parseKidView } from "../types";
import midgame from "../__fixtures__/midgame.json";
import terminal from "../__fixtures__/terminal.json";
import { MapBoard } from "./MapBoard";

const mid = (over: Record<string, unknown> = {}): KidView =>
  parseKidView({ ...midgame, ...over });

describe("MapBoard", () => {
  it("labels all 8 regions with counts and state", () => {
    render(<MapBoard v={mid()} />);
    const names = ["Moray", "Strathclyde", "Lancaster", "Northumbria", "Gwynedd", "Warwick", "Essex", "Devon"];
    names.forEach((n, i) => {
      const g = screen.getByTestId(`region-${i}`);
      expect(within(g).getByText(n)).toBeInTheDocument();
    });
    expect(screen.getByLabelText("Gwynedd: 1 Scottish, 4 Welsh, 1 English; open")).toBeInTheDocument();
    const gw = screen.getByTestId("region-4");
    expect(within(gw).getByText("×4")).toBeInTheDocument();
    expect(gw).toHaveAttribute("data-state", "open");
    // Devon has no Scottish followers: only two chips.
    expect(within(screen.getByTestId("region-7")).queryByTestId("followers-0")).toBeNull();
  });

  it("shows the track with the next slot emphasised", () => {
    render(<MapBoard v={mid()} />);
    for (let i = 0; i < 8; i++) expect(screen.getByTestId(`track-slot-${i}`)).toHaveAttribute("data-face-down", "false");
    expect(screen.getByTestId("track-slot-0")).toHaveAttribute("data-current", "true");
    expect(screen.getByTestId("track-slot-1")).not.toHaveAttribute("data-current");
    expect(screen.getByTestId("region-1")).toHaveAttribute("data-current", "true");
    expect(screen.getByLabelText("Slot 1: Strathclyde, pending")).toBeInTheDocument();
  });

  it("renders the terminal board: face-down cards, discs, control and unstable markers", () => {
    render(<MapBoard v={parseKidView(terminal)} />);
    for (let i = 0; i < 8; i++) expect(screen.getByTestId(`track-slot-${i}`)).toHaveAttribute("data-face-down", "true");
    expect(screen.getByTestId("track-slot-4")).toHaveAttribute("data-face-down", "true");
    expect(screen.getByTestId("disc-4-1")).toBeInTheDocument();
    expect(screen.getByTestId("disc-7-0")).toBeInTheDocument();
    expect(screen.getByTestId("region-0")).toHaveAttribute("data-state", "unstable");
    expect(screen.getByTestId("unstable-0")).toBeInTheDocument();
    expect(screen.getByTestId("state-0")).toHaveTextContent("Unstable");
    expect(screen.getByTestId("region-4")).toHaveAttribute("data-state", "controlled");
    expect(screen.getByTestId("control-4")).toBeInTheDocument();
    expect(screen.getByTestId("state-4")).toHaveTextContent("Controlled by Welsh");
    expect(screen.getByLabelText(/^Moray: .*unstable$/)).toBeInTheDocument();
    expect(screen.queryByTestId("track-slot-0")?.getAttribute("data-current")).toBeNull();
    expect(screen.queryByTestId("assemble-banner")).toBeNull();
  });

  it("shows the follower type being placed in Assemble", () => {
    const v = mid({ pending: { ...midgame.pending, assemble_faction: 1 } });
    render(<MapBoard v={v} />);
    const banner = screen.getByTestId("assemble-banner");
    expect(banner).toHaveAttribute("role", "status");
    expect(within(banner).getByText("Placing Welsh followers")).toBeInTheDocument();
    expect(within(banner).getByText("W")).toBeInTheDocument();
  });

  it("supports optional click and highlight hooks", () => {
    const onClick = vi.fn();
    const { rerender } = render(<MapBoard v={mid()} />);
    expect(screen.getByTestId("region-2")).toHaveAttribute("role", "group");
    expect(screen.queryByTestId("highlight-2")).toBeNull();
    rerender(<MapBoard v={mid()} onRegionClick={onClick} highlightRegions={new Set([2])} />);
    fireEvent.click(screen.getByTestId("region-2"));
    expect(onClick).toHaveBeenCalledWith(2);
    expect(screen.getByTestId("highlight-2")).toBeInTheDocument();
  });

  it("draws one road per R-002 neighbour pair", () => {
    render(<MapBoard v={mid()} />);
    expect(screen.getByTestId("roads").querySelectorAll("[data-border]")).toHaveLength(13);
  });
});
