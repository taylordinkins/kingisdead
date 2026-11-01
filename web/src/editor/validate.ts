/**
 * Synchronous port of the scenario validations V1..V11 (docs/SCENARIOS.md section 3,
 * kingisdead/scenario.py). Unlike the Python loader, which stops at the first failure,
 * this collects every issue so a UI can show them all live.
 *
 * V5 (each region_state value is S/W/E/unstable) is enforced by the model's types and the
 * JSON parser (ScenarioParseError), so `validate` never reports it.
 */
import {
  CARDS,
  CARDS_PER_HAND,
  FACTIONS,
  HOME_REGION,
  REGIONS,
  STARTING_HAND_COUNTS,
  poolSize,
  sum,
  type Card,
  type Faction,
  type Region,
  type RegionCounts,
  type RegionStates,
  type ScenarioModel,
} from "./model";

export type IssueCode = "V1" | "V2" | "V3" | "V4" | "V5" | "V6" | "V7" | "V8" | "V9" | "V10" | "V11" | "RANGE";

export interface Issue {
  /** V1..V11, or RANGE for plain range errors (to_play, struggles) that scenario.py rejects without a V-code. */
  code: IssueCode;
  message: string;
  /** Model field paths the issue concerns, e.g. ["regions.Moray", "courts.0"]. */
  fields: string[];
}

const closedRegions = (s: RegionStates): Region[] => REGIONS.filter((r) => s[r] !== undefined);
const regionTotal = (r: RegionCounts, f: Faction): number => REGIONS.reduce((a, name) => a + r[name][f], 0);

function checkPool(
  issues: Issue[],
  regions: RegionCounts,
  courts: ScenarioModel["courts"],
  pool: number,
  what: string,
  prefix: string,
): void {
  for (const f of FACTIONS) {
    const total = regionTotal(regions, f) + courts.reduce((a, c) => a + c[f], 0);
    if (total > pool) {
      issues.push({
        code: "V1",
        message: `${what}: faction ${f} has ${total} followers, pool is ${pool}`,
        fields: [`${prefix}regions`, `${prefix}courts`],
      });
    }
  }
}

function checkClosedEmpty(
  issues: Issue[],
  regions: RegionCounts,
  states: RegionStates,
  what: string,
  prefix: string,
): void {
  for (const r of closedRegions(states)) {
    if (sum(regions[r]) > 0) {
      issues.push({
        code: "V2",
        message: `${what}: closed region ${r} holds followers`,
        fields: [`${prefix}regions.${r}`, `${prefix}regionState.${r}`],
      });
    }
  }
}

export function validate(m: ScenarioModel): Issue[] {
  const issues: Issue[] = [];
  const n = m.players;
  const pool = poolSize(n);
  checkPool(issues, m.regions, m.courts, pool, "board", "");
  if (m.kind === "setup") {
    validateSetup(m, issues);
    return issues;
  }

  const closed = closedRegions(m.regionState);
  const unstable = closed.filter((r) => m.regionState[r] === "unstable");
  const { struggles } = m;
  if (!Number.isInteger(struggles) || struggles < 0 || struggles > 8) {
    issues.push({ code: "RANGE", message: "struggles must be 0..8", fields: ["struggles"] });
  }
  checkClosedEmpty(issues, m.regions, m.regionState, "board", "");
  const terminalInvasion =
    unstable.length === 3 && struggles >= 1 && unstable.includes(m.slots[struggles - 1] as Region);
  if (unstable.length >= 3 && !terminalInvasion) {
    issues.push({ code: "V3", message: "three unstable regions on a non-terminal board", fields: ["regionState"] });
  }
  const firstN = m.slots.slice(0, Math.max(0, struggles));
  if (closed.length !== struggles || [...closed].sort().join() !== [...firstN].sort().join()) {
    issues.push({
      code: "V4",
      message: "closed regions must be exactly the regions in slots 1..struggles",
      fields: ["struggles", "regionState", "slots"],
    });
  }

  // V8 and hand sizes.
  m.hands.forEach((h, p) => {
    for (const c of CARDS) {
      const k = h.filter((x) => x === c).length;
      if (k > STARTING_HAND_COUNTS[c]) {
        issues.push({
          code: "V8",
          message: `player ${p} holds ${k} copies of ${c}`,
          fields: [`hands.${p}`],
        });
      }
    }
  });
  const sizes = m.hands.map((h) => h.length);
  const played = sizes.map((s) => CARDS_PER_HAND - s);
  const total = played.reduce((a, b) => a + b, 0);

  // V6
  const seen = new Map<Region, number>();
  m.negotiation.forEach((x, p) => {
    if (x === null) return;
    if (seen.has(x)) {
      issues.push({
        code: "V6",
        message: `players ${seen.get(x)} and ${p} name the same region`,
        fields: [`negotiation.${seen.get(x)}`, `negotiation.${p}`],
      });
    } else seen.set(x, p);
    if (m.hands[p]?.includes("negotiate")) {
      issues.push({
        code: "V6",
        message: `player ${p} has a spent disc but still holds negotiate`,
        fields: [`negotiation.${p}`, `hands.${p}`],
      });
    }
  });

  // V9 and to_play range
  if (!Number.isInteger(m.passCount) || m.passCount < 0 || m.passCount >= n) {
    issues.push({ code: "V9", message: "pass_count must be < players", fields: ["passCount"] });
  }
  if (!Number.isInteger(m.toPlay) || m.toPlay < 0 || m.toPlay >= n) {
    issues.push({ code: "RANGE", message: "to_play out of range", fields: ["toPlay"] });
  }

  validateRecords(m, played, sizes, total, issues);
  validateLastCard(m, total, issues, pool);
  return issues;
}

function validateRecords(m: ScenarioModel, played: number[], sizes: number[], total: number, issues: Issue[]): void {
  const push = (message: string, fields: string[]): number => issues.push({ code: "V7", message, fields });
  const vals = m.lastPlay.filter((v): v is number => v !== null);
  if (new Set(vals).size !== vals.length || vals.some((v) => !Number.isInteger(v) || v < 1 || v > total)) {
    push("last_play values must be distinct integers in 1..total", ["lastPlay"]);
  }
  m.lastPlay.forEach((v, p) => {
    if ((v === null) !== (played[p] === 0) || (v !== null && v < (played[p] as number))) {
      push(`last_play[${p}] inconsistent with cards played`, [`lastPlay.${p}`, `hands.${p}`]);
    }
  });
  if (total > 0 && vals.length > 0 && Math.max(...vals) !== total) {
    push("largest last_play must equal the card-play total", ["lastPlay"]);
  }
  m.handEmpty.forEach((v, p) => {
    if ((v !== null) !== (sizes[p] === 0) || (v !== null && v !== m.lastPlay[p])) {
      push(`hand_empty[${p}] inconsistent`, [`handEmpty.${p}`, `hands.${p}`, `lastPlay.${p}`]);
    }
  });
}

function validateLastCard(m: ScenarioModel, total: number, issues: Issue[], pool: number): void {
  const lc = m.lastCard;
  if ((lc === null) !== (total === 0)) {
    issues.push({
      code: "V10",
      message: "last_card must be null exactly when no card has been played",
      fields: ["lastCard"],
    });
  }
  if (lc === null) return;
  const mover = m.lastPlay.indexOf(total);
  if (mover >= 0) {
    const held = (m.hands[mover] ?? []).filter((c: Card) => c === lc.type).length;
    if (held >= STARTING_HAND_COUNTS[lc.type]) {
      issues.push({
        code: "V10",
        message: "last_card type is still fully in the last player's hand",
        fields: ["lastCard.type", `hands.${mover}`],
      });
    }
  }
  const rb = lc.referenceBoard;
  if (rb) {
    if (lc.type !== "manoeuvre" && lc.type !== "outmanoeuvre") {
      issues.push({
        code: "V10",
        message: "reference_board only allowed for manoeuvre/outmanoeuvre",
        fields: ["lastCard.referenceBoard", "lastCard.type"],
      });
    }
    checkPool(issues, rb.regions, m.courts, pool, "reference_board", "lastCard.referenceBoard.");
    checkClosedEmpty(issues, rb.regions, rb.regionState, "reference_board", "lastCard.referenceBoard.");
  }
}

function validateSetup(m: ScenarioModel, issues: Issue[]): void {
  for (const r of REGIONS) {
    const t = sum(m.regions[r]);
    if (t !== 4) {
      issues.push({ code: "V11", message: `${r} holds ${t} followers, expected 4`, fields: [`regions.${r}`] });
    }
  }
  for (const f of FACTIONS) {
    const home = HOME_REGION[f];
    if (m.regions[home][f] < 2) {
      issues.push({ code: "V11", message: `${home} needs >= 2 ${f}`, fields: [`regions.${home}.${f}`] });
    }
  }
  m.courts.forEach((c, p) => {
    if (sum(c) !== 2) {
      issues.push({ code: "V11", message: "each court must hold exactly 2 followers", fields: [`courts.${p}`] });
    }
  });
}

export interface Summary {
  pool: number;
  /** Followers of each faction on the board / in courts / left in supply (can be negative if V1 fails). */
  onBoard: Record<Faction, number>;
  inCourts: Record<Faction, number>;
  supply: Record<Faction, number>;
  /** Follower total per region. */
  regionTotals: Record<Region, number>;
  /** Total followers in each player's court. */
  courtTotals: number[];
  /** Cards played in total (V7) = sum of 8 - hand size. */
  cardPlays: number;
  /** Instability discs on the board. */
  unstableDiscs: number;
  /** Slot numbers (1-based) that are face down: 1..struggles (V4). */
  faceDownSlots: number[];
  /** Each faction's most recent win (R-303): highest slot <= struggles it controls, -1 if none. */
  recentWin: Record<Faction, number>;
}

/** Derived numbers for the UI. Cheap and total: never throws on an invalid model. */
export function summarize(m: ScenarioModel): Summary {
  const pool = poolSize(m.players);
  const per = (fn: (f: Faction) => number): Record<Faction, number> => ({ S: fn("S"), W: fn("W"), E: fn("E") });
  const onBoard = per((f) => regionTotal(m.regions, f));
  const inCourts = per((f) => m.courts.reduce((a, c) => a + c[f], 0));
  const struggles = m.kind === "state" ? Math.max(0, Math.min(8, m.struggles)) : 0;
  const recentWin: Record<Faction, number> = { S: -1, W: -1, E: -1 };
  for (let k = 1; k <= struggles; k++) {
    const st = m.regionState[m.slots[k - 1] as Region];
    if (st === "S" || st === "W" || st === "E") recentWin[st] = k;
  }
  return {
    pool,
    onBoard,
    inCourts,
    supply: per((f) => pool - onBoard[f] - inCourts[f]),
    regionTotals: Object.fromEntries(REGIONS.map((r) => [r, sum(m.regions[r])])) as Record<Region, number>,
    courtTotals: m.courts.map(sum),
    cardPlays: m.kind === "state" ? m.hands.reduce((a, h) => a + (CARDS_PER_HAND - h.length), 0) : 0,
    unstableDiscs: m.kind === "state" ? REGIONS.filter((r) => m.regionState[r] === "unstable").length : 0,
    faceDownSlots: Array.from({ length: struggles }, (_, i) => i + 1),
    recentWin,
  };
}
