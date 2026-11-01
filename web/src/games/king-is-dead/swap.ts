/**
 * Click-order independence for symmetric swaps (Manoeuvre, Outmanoeuvre 1-for-1, Negotiate).
 * The engine wants the lower region first; the server lists every legal canonical pair in
 * `view.swap_pairs`, and the board lets the player click either follower first.
 */
export interface SwapPick {
  id: number;
  region: number;
  /** Null for a region-card pick (Negotiate). */
  faction: number | null;
}
/** [lower-region pick, higher-region pick]: the canonical action order. */
export type SwapPair = [SwapPick, SwapPick];

/** Every follower that appears in some legal swap, in either role, deduplicated by action id. */
export function firstPicks(pairs: readonly SwapPair[]): SwapPick[] {
  const seen = new Map<number, SwapPick>();
  for (const [a, b] of pairs) {
    seen.set(a.id, a);
    seen.set(b.id, b);
  }
  return [...seen.values()];
}

/** Followers that complete a legal swap with the one already chosen (`held`, an action id). */
export function partnersOf(pairs: readonly SwapPair[], held: number): SwapPick[] {
  const seen = new Map<number, SwapPick>();
  for (const [a, b] of pairs) {
    if (a.id === held) seen.set(b.id, b);
    else if (b.id === held) seen.set(a.id, a);
  }
  return [...seen.values()];
}

/** The two action ids to submit, in canonical order, for a swap of the two clicked followers. */
export function canonicalSequence(
  pairs: readonly SwapPair[],
  x: number,
  y: number,
): [number, number] | null {
  for (const [a, b] of pairs) {
    if ((a.id === x && b.id === y) || (a.id === y && b.id === x)) return [a.id, b.id];
  }
  return null;
}

export function parseSwapPairs(raw: unknown): SwapPair[] {
  if (!Array.isArray(raw)) return [];
  const pick = (p: unknown): SwapPick | null => {
    if (typeof p !== "object" || p === null) return null;
    const o = p as Record<string, unknown>;
    if (!Number.isInteger(o.id) || !Number.isInteger(o.region)) return null;
    if (o.faction !== undefined && !Number.isInteger(o.faction)) return null;
    return {
      id: o.id as number,
      region: o.region as number,
      faction: o.faction === undefined ? null : (o.faction as number),
    };
  };
  const out: SwapPair[] = [];
  for (const pr of raw) {
    if (!Array.isArray(pr) || pr.length !== 2) continue;
    const a = pick(pr[0]);
    const b = pick(pr[1]);
    if (a && b) out.push([a, b]);
  }
  return out;
}

/** A first swap pick held client-side, tagged with the position it was made in. */
export interface HeldPick {
  id: number;
  key: string;
}

export function positionKey(
  historyLength: number,
  currentPlayer: number | null,
  phase: string,
  swapPicks: number,
): string {
  return `${historyLength}|${currentPlayer}|${phase}|${swapPicks}`;
}

/** The held action id, or null when it was made in a different position (stale). */
export function activeHeld(held: HeldPick | null, key: string): number | null {
  return held !== null && held.key === key ? held.id : null;
}
