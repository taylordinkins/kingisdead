import { describe, expect, it } from "vitest";
import { SEAT_PRESETS, seatTypeName, thinkingText } from "./seatTypes";

describe("seat presets", () => {
  it("offers human, random, heuristic and three MCTS strengths and the trained model", () => {
    expect(SEAT_PRESETS.map((p) => p.value)).toEqual([
      "human",
      "random",
      "heuristic",
      "mcts:20",
      "mcts:100",
      "mcts:400",
      "trained:az-2p-v1",
    ]);
  });
  it("names seat types", () => {
    expect(seatTypeName("heuristic")).toBe("Heuristic");
    expect(seatTypeName("mcts:100")).toBe("MCTS Medium");
    expect(seatTypeName("mcts:50")).toBe("MCTS (50 sims)");
    expect(seatTypeName("mcts")).toBe("MCTS");
  });
  it("builds the thinking text", () => {
    expect(thinkingText("heuristic", 1)).toBe("Heuristic (P1) is thinking…");
  });
});
