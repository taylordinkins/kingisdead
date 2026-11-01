import { describe, expect, it } from "vitest";
import { canonicalSequence, firstPicks, parseSwapPairs, partnersOf, type SwapPair } from "./swap";

const p = (id: number, region: number, faction: number) => ({ id, region, faction });
// Warwick(5) Scot with Moray(0) Scot / Essex(6) Welsh; canonical = lower region first.
const pairs: SwapPair[] = [
  [p(10, 0, 0), p(50, 5, 0)],
  [p(10, 0, 0), p(61, 6, 1)],
  [p(50, 5, 0), p(61, 6, 1)],
];

describe("swap click ordering", () => {
  it("offers every follower in any legal swap as a first pick", () => {
    expect(firstPicks(pairs).map((x) => x.id).sort((a, b) => a - b)).toEqual([10, 50, 61]);
  });
  it("offers partners in both roles (lower and higher region)", () => {
    expect(partnersOf(pairs, 50).map((x) => x.id).sort((a, b) => a - b)).toEqual([10, 61]);
  });
  it("submits canonical order whichever follower was clicked first", () => {
    expect(canonicalSequence(pairs, 50, 10)).toEqual([10, 50]);
    expect(canonicalSequence(pairs, 10, 50)).toEqual([10, 50]);
    expect(canonicalSequence(pairs, 61, 50)).toEqual([50, 61]);
  });
  it("rejects a non-legal combination", () => {
    expect(canonicalSequence(pairs, 10, 99)).toBeNull();
  });
  it("parses server payloads and ignores junk", () => {
    const raw = [[{ id: 1, region: 0, faction: 0, label: "x" }, { id: 2, region: 1, faction: 2 }], [1], "z"];
    expect(parseSwapPairs(raw)).toEqual([[p(1, 0, 0), p(2, 1, 2)]]);
    expect(parseSwapPairs(undefined)).toEqual([]);
  });
});
