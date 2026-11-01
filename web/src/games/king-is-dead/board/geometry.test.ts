import { describe, expect, it } from "vitest";
import { DRAWN_BORDERS, REGION_SHAPES } from "./geometry";

// R-002 adjacency, copied from docs/RULES_SPEC.md.
const ADJ: Record<number, number[]> = {
  0: [1],
  1: [0, 2, 3],
  2: [1, 3, 4, 5],
  3: [1, 2, 5, 6],
  4: [2, 5, 7],
  5: [2, 3, 4, 6, 7],
  6: [3, 5, 7],
  7: [4, 5, 6],
};

describe("map geometry", () => {
  it("covers all 8 regions exactly once with R-001 names", () => {
    expect(REGION_SHAPES.map((r) => r.index)).toEqual([0, 1, 2, 3, 4, 5, 6, 7]);
    expect(REGION_SHAPES.map((r) => r.name)).toEqual([
      "Moray", "Strathclyde", "Lancaster", "Northumbria", "Gwynedd", "Warwick", "Essex", "Devon",
    ]);
    for (const r of REGION_SHAPES) expect(r.points.length).toBeGreaterThanOrEqual(3);
  });

  it("draws exactly the R-002 neighbour pairs", () => {
    const key = (a: number, b: number) => `${Math.min(a, b)}-${Math.max(a, b)}`;
    const drawn = DRAWN_BORDERS.map(([a, b]) => key(a, b)).sort();
    const spec = Object.entries(ADJ)
      .flatMap(([a, bs]) => bs.map((b) => key(Number(a), b)))
      .filter((k, i, all) => all.indexOf(k) === i)
      .sort();
    expect(drawn).toEqual(spec);
    expect(new Set(drawn).size).toBe(drawn.length);
  });
});
