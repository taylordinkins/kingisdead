import { render, screen, within } from "@testing-library/react";
import ScoringPanel from "./ScoringPanel";
import type { KidView, Scoring } from "./types";

const names = ["Scottish", "Welsh", "English"];
const fname = (f: number | null) => (f === null ? "none" : names[f]!);

function panel(scoring: Scoring, winners: number[]) {
  const v = { faction_names: names, is_terminal: true, winners, returns: [0, 0], scoring } as unknown as KidView;
  render(<ScoringPanel v={v} fname={fname} />);
  return screen.getByLabelText("Result");
}

describe("ScoringPanel", () => {
  it("skips an undefined rank-2 step and says why", () => {
    const r = panel(
      {
        mode: "coronation",
        faction_ranking: [0, null, null],
        regions_controlled: [6, 0, 0],
        recent_win: [6, -1, -1],
        winners: [1],
        steps: [
          { name: "rank_1_followers", faction: 0, values: [2, 2], tied_before: [0, 1], remaining: [0, 1] },
          { name: "rank_2_followers", faction: null, skipped: true },
          { name: "hand_emptied", faction: null, values: [9, 4], tied_before: [0, 1], remaining: [1] },
        ],
      },
      [1],
    );
    expect(within(r).getByText(/skipped \(rank 2 faction is undefined/)).toBeInTheDocument();
    expect(within(r).getByText(/P1 decides/)).toBeInTheDocument();
    expect(within(r).getByLabelText("Winners")).toHaveTextContent("Winner(s): P1");
    expect(within(r).getByText(/ranks? 2 and 3 undefined/)).toBeInTheDocument();
  });

  it("reports a shared win when nobody emptied their hand", () => {
    const r = panel(
      {
        mode: "coronation",
        faction_ranking: [0, 1, 2],
        regions_controlled: [3, 3, 2],
        recent_win: [8, 5, 7],
        winners: [0, 1],
        steps: [
          { name: "hand_emptied", faction: null, values: [null, null], tied_before: [0, 1], remaining: [0, 1] },
        ],
      },
      [0, 1],
    );
    expect(within(r).getByLabelText("Winners")).toHaveTextContent("(shared win)");
    expect(within(r).getByText(/share the win \(nobody emptied their hand\)/)).toBeInTheDocument();
    expect(within(r).getByText(/P0 never, P1 never/)).toBeInTheDocument();
  });

  it("only the last step says share the win in a tie chain", () => {
    const r = panel(
      {
        mode: "coronation",
        faction_ranking: [0, 1, 2],
        regions_controlled: [4, 3, 1],
        recent_win: [8, 5, 7],
        winners: [0, 1],
        steps: [
          { name: "rank_1_followers", faction: 0, values: [2, 2, 1], tied_before: [0, 1, 2], remaining: [0, 1] },
          { name: "rank_2_followers", faction: 1, values: [3, 3, 0], tied_before: [0, 1], remaining: [0, 1] },
          { name: "hand_emptied", faction: null, values: [null, null, 5], tied_before: [0, 1], remaining: [0, 1] },
        ],
      },
      [0, 1],
    );
    expect(within(r).getAllByText(/still tied: P0, P1$/)).toHaveLength(2);
    expect(within(r).getAllByText(/share the win/)).toHaveLength(1);
    expect(within(r).getByText(/share the win \(nobody emptied their hand\)/)).toBeInTheDocument();
  });

  it("explains invasion steps", () => {
    const r = panel(
      {
        mode: "invasion",
        winners: [0],
        steps: [{ name: "complete_sets", faction: null, values: [2, 1], tied_before: [0, 1], remaining: [0] }],
      },
      [0],
    );
    expect(within(r).getByText(/invasion: three unstable regions/)).toBeInTheDocument();
    expect(within(r).getByText(/P0 decides/)).toBeInTheDocument();
  });
});
