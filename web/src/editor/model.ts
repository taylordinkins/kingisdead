/**
 * Typed editor model of a scenario (docs/SCENARIOS.md). Pure data and pure helpers; no React.
 * Mirrors the JSON format but with every default filled in, so the UI never deals with absent keys.
 */

export const REGIONS = [
  "Moray",
  "Strathclyde",
  "Lancaster",
  "Northumbria",
  "Gwynedd",
  "Warwick",
  "Essex",
  "Devon",
] as const;
export type Region = (typeof REGIONS)[number];

export const FACTIONS = ["S", "W", "E"] as const;
export type Faction = (typeof FACTIONS)[number];

export const CARDS = [
  "scottish_support",
  "welsh_support",
  "english_support",
  "assemble",
  "negotiate",
  "manoeuvre",
  "outmanoeuvre",
] as const;
export type Card = (typeof CARDS)[number];

/** Copies of each card in a full starting hand (R-008). */
export const STARTING_HAND_COUNTS: Readonly<Record<Card, number>> = {
  scottish_support: 1,
  welsh_support: 1,
  english_support: 1,
  assemble: 2,
  negotiate: 1,
  manoeuvre: 1,
  outmanoeuvre: 1,
};
export const CARDS_PER_HAND = 8;

/** Followers per faction in the pool (R-005). */
export function poolSize(players: number): number {
  return players === 2 ? 16 : 18;
}

/** Home region of each faction (R-011). */
export const HOME_REGION: Readonly<Record<Faction, Region>> = { S: "Moray", W: "Gwynedd", E: "Essex" };

export type Counts = Record<Faction, number>;
export type RegionState = Faction | "unstable";
export type RegionCounts = Record<Region, Counts>;
export type RegionStates = Partial<Record<Region, RegionState>>;

export interface ReferenceBoard {
  regions: RegionCounts;
  regionState: RegionStates;
}

export interface LastCard {
  type: Card;
  /** B* (R-216); null means omitted, i.e. void (D22). Only meaningful for (out)manoeuvre. */
  referenceBoard: ReferenceBoard | null;
}

export type Kind = "setup" | "state";

export interface ScenarioModel {
  kind: Kind;
  description: string;
  players: 2 | 3;
  /** slots[i] is the region on the card in slot i+1 (R-010); a permutation of REGIONS. */
  slots: Region[];
  regions: RegionCounts;
  courts: Counts[];
  // State-only fields (ignored and omitted for kind "setup").
  toPlay: number;
  struggles: number;
  regionState: RegionStates;
  negotiation: (Region | null)[];
  hands: Card[][];
  passCount: number;
  lastPlay: (number | null)[];
  handEmpty: (number | null)[];
  lastCard: LastCard | null;
  /** Opaque worked example block (SCENARIOS.md section 4); preserved verbatim. */
  example: unknown;
}

export const emptyCounts = (): Counts => ({ S: 0, W: 0, E: 0 });
export const emptyRegionCounts = (): RegionCounts =>
  Object.fromEntries(REGIONS.map((r) => [r, emptyCounts()])) as RegionCounts;
export const fullHand = (): Card[] => CARDS.flatMap((c) => Array<Card>(STARTING_HAND_COUNTS[c]).fill(c));
export const sum = (c: Counts): number => c.S + c.W + c.E;

function blank(kind: Kind, players: 2 | 3): ScenarioModel {
  return {
    kind,
    description: "",
    players,
    slots: [...REGIONS],
    regions: emptyRegionCounts(),
    courts: Array.from({ length: players }, emptyCounts),
    toPlay: 0,
    struggles: 0,
    regionState: {},
    negotiation: Array<Region | null>(players).fill(null),
    hands: Array.from({ length: players }, fullHand),
    passCount: 0,
    lastPlay: Array<number | null>(players).fill(null),
    handEmpty: Array<number | null>(players).fill(null),
    lastCard: null,
    example: undefined,
  };
}

/** Blank new setup scenario (empty board and courts; the user fills it in to satisfy V11). */
export const newSetupModel = (players: 2 | 3): ScenarioModel => blank("setup", players);
/** Blank new state scenario at the R-014 start values. */
export const newStateModel = (players: 2 | 3): ScenarioModel => blank("state", players);

// ---------------------------------------------------------------------------------------------
// Pure mutation helpers: each returns a new model and never changes its argument.
// ---------------------------------------------------------------------------------------------

const clampCount = (n: number): number => Math.max(0, Math.trunc(n));

export function setDescription(m: ScenarioModel, description: string): ScenarioModel {
  return { ...m, description };
}

export function setKind(m: ScenarioModel, kind: Kind): ScenarioModel {
  return { ...m, kind };
}

/** Change the player count, resizing every per-player list (new entries take defaults). */
export function setPlayers(m: ScenarioModel, players: 2 | 3): ScenarioModel {
  const fit = <T>(xs: T[], make: () => T): T[] =>
    Array.from({ length: players }, (_, i) => (i < xs.length ? (xs[i] as T) : make()));
  return {
    ...m,
    players,
    courts: fit(m.courts, emptyCounts).map((c) => ({ ...c })),
    negotiation: fit(m.negotiation, () => null),
    hands: fit(m.hands, fullHand).map((h) => [...h]),
    lastPlay: fit(m.lastPlay, () => null),
    handEmpty: fit(m.handEmpty, () => null),
    toPlay: Math.min(m.toPlay, players - 1),
    passCount: Math.min(m.passCount, players - 1),
  };
}

export function setFollowers(m: ScenarioModel, region: Region, faction: Faction, n: number): ScenarioModel {
  return { ...m, regions: { ...m.regions, [region]: { ...m.regions[region], [faction]: clampCount(n) } } };
}

export function setCourtFollowers(m: ScenarioModel, player: number, faction: Faction, n: number): ScenarioModel {
  return { ...m, courts: m.courts.map((c, i) => (i === player ? { ...c, [faction]: clampCount(n) } : c)) };
}

/** Move the region card at track position `from` to position `to` (0-based), shifting the others. */
export function moveCard(m: ScenarioModel, from: number, to: number): ScenarioModel {
  if (from === to || from < 0 || to < 0 || from >= m.slots.length || to >= m.slots.length) return m;
  const slots = [...m.slots];
  const [card] = slots.splice(from, 1);
  slots.splice(to, 0, card as Region);
  return { ...m, slots };
}

/** Swap the region cards at two track positions (0-based). */
export function swapCards(m: ScenarioModel, a: number, b: number): ScenarioModel {
  if (a === b || !m.slots[a] || !m.slots[b]) return m;
  const slots = [...m.slots];
  [slots[a], slots[b]] = [slots[b] as Region, slots[a] as Region];
  return { ...m, slots };
}

export function setToPlay(m: ScenarioModel, toPlay: number): ScenarioModel {
  return { ...m, toPlay };
}
export function setStruggles(m: ScenarioModel, struggles: number): ScenarioModel {
  return { ...m, struggles };
}
export function setPassCount(m: ScenarioModel, passCount: number): ScenarioModel {
  return { ...m, passCount };
}

/** Set (or with `undefined` clear back to open) the closed state of a region. */
export function setRegionState(m: ScenarioModel, region: Region, state: RegionState | undefined): ScenarioModel {
  const regionState = { ...m.regionState };
  if (state === undefined) delete regionState[region];
  else regionState[region] = state;
  return { ...m, regionState };
}

export function setNegotiation(m: ScenarioModel, player: number, region: Region | null): ScenarioModel {
  return { ...m, negotiation: m.negotiation.map((x, i) => (i === player ? region : x)) };
}

export function setLastPlay(m: ScenarioModel, player: number, value: number | null): ScenarioModel {
  return { ...m, lastPlay: m.lastPlay.map((x, i) => (i === player ? value : x)) };
}

export function setHandEmpty(m: ScenarioModel, player: number, value: number | null): ScenarioModel {
  return { ...m, handEmpty: m.handEmpty.map((x, i) => (i === player ? value : x)) };
}

export function setHand(m: ScenarioModel, player: number, hand: Card[]): ScenarioModel {
  return { ...m, hands: m.hands.map((h, i) => (i === player ? [...hand] : h)) };
}

/** Add one copy of `card` to a hand (no cap; V8 reports overfull hands). */
export function addCard(m: ScenarioModel, player: number, card: Card): ScenarioModel {
  return setHand(m, player, [...(m.hands[player] ?? []), card]);
}

/** Remove one copy of `card` from a hand, if present. */
export function removeCard(m: ScenarioModel, player: number, card: Card): ScenarioModel {
  const hand = [...(m.hands[player] ?? [])];
  const i = hand.indexOf(card);
  if (i >= 0) hand.splice(i, 1);
  return setHand(m, player, hand);
}

export function setLastCard(m: ScenarioModel, lastCard: LastCard | null): ScenarioModel {
  return { ...m, lastCard };
}

export function setReferenceBoard(m: ScenarioModel, referenceBoard: ReferenceBoard | null): ScenarioModel {
  return m.lastCard ? { ...m, lastCard: { ...m.lastCard, referenceBoard } } : m;
}

export function setExample(m: ScenarioModel, example: unknown): ScenarioModel {
  return { ...m, example };
}
