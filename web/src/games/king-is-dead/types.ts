/** Hand-written mirror of server/adapters/kingisdead.py `view()`. Game-specific types live only here. */

export const FACTION_NAMES = ["Scottish", "Welsh", "English"] as const;
export const CARD_NAMES: Record<string, string> = {
  "1": "Scottish Support",
  "2": "Welsh Support",
  "3": "English Support",
  "4": "Assemble",
  "5": "Negotiate",
  "6": "Manoeuvre",
  "7": "Outmanoeuvre",
};

export interface Region {
  region: number;
  name: string;
  /** Followers present, per faction. */
  followers: number[];
  state: "open" | "controlled" | "unstable";
  controller: number | null;
}

export interface TrackSlot {
  slot: number;
  region: number | null;
  face_down: boolean;
  discs: number[];
}

export interface Pending {
  card: number | null;
  assemble_faction: number | null;
  neg_first: number | null;
  neg_second: number | null;
  swap_mode: unknown;
  swap_picks: number[][];
}

export interface ScoringStep {
  name: string;
  faction: number | null;
  skipped?: boolean;
  values?: (number | null)[];
  tied_before?: number[];
  remaining?: number[];
}

export interface Scoring {
  mode: "invasion" | "coronation";
  steps: ScoringStep[];
  winners: number[];
  faction_ranking?: (number | null)[];
  regions_controlled?: number[];
  recent_win?: number[];
}

export interface KidView {
  seat: number;
  num_players: number;
  regions: Region[];
  track: TrackSlot[];
  supply: number[];
  /** courts[player][faction] */
  courts: number[][];
  /** hands[player]: card id -> count */
  hands: Record<string, number>[];
  negotiation_discs: (number | null)[];
  current_player: number | null;
  is_chance: boolean;
  is_terminal: boolean;
  stage: string;
  phase: string;
  pending: Pending;
  consecutive_passes: number;
  struggles_resolved: number;
  returns?: number[];
  winners?: number[];
  scoring?: Scoring;
}

type Rec = Record<string, unknown>;
const isRec = (v: unknown): v is Rec => typeof v === "object" && v !== null && !Array.isArray(v);
const isInt = (v: unknown): v is number => typeof v === "number" && Number.isInteger(v);
const isIntOrNull = (v: unknown): boolean => v === null || isInt(v);
const isIntArr = (v: unknown): v is number[] => Array.isArray(v) && v.every(isInt);
const isArrOf = (v: unknown, f: (x: unknown) => boolean): boolean => Array.isArray(v) && v.every(f);

function fail(what: string): never {
  throw new Error(`unexpected "${what}" in King is Dead view`);
}

/** Returns the view typed, or throws an Error naming the first bad field. */
export function parseKidView(raw: unknown): KidView {
  if (!isRec(raw)) fail("view (not an object)");
  const need = (key: string, ok: (v: unknown) => boolean) => {
    if (!ok(raw[key])) fail(key);
  };
  need("num_players", isInt);
  need("seat", isInt);
  need("regions", (v) =>
    isArrOf(
      v,
      (r) =>
        isRec(r) &&
        isInt(r.region) &&
        typeof r.name === "string" &&
        isIntArr(r.followers) &&
        (r.state === "open" || r.state === "controlled" || r.state === "unstable") &&
        isIntOrNull(r.controller),
    ),
  );
  need("track", (v) =>
    isArrOf(
      v,
      (t) =>
        isRec(t) &&
        isInt(t.slot) &&
        isIntOrNull(t.region) &&
        typeof t.face_down === "boolean" &&
        isIntArr(t.discs),
    ),
  );
  need("supply", isIntArr);
  need("courts", (v) => isArrOf(v, isIntArr));
  need("hands", (v) => isArrOf(v, (h) => isRec(h) && Object.values(h).every(isInt)));
  need("negotiation_discs", (v) => isArrOf(v, isIntOrNull));
  need("current_player", isIntOrNull);
  need("is_terminal", (v) => typeof v === "boolean");
  need("stage", (v) => typeof v === "string");
  need("phase", (v) => typeof v === "string");
  need("pending", isRec);
  need("consecutive_passes", isInt);
  need("struggles_resolved", isInt);
  if (raw.returns !== undefined) need("returns", (v) => isArrOf(v, (x) => typeof x === "number"));
  if (raw.winners !== undefined) need("winners", isIntArr);
  if (raw.scoring !== undefined) {
    need(
      "scoring",
      (v) =>
        isRec(v) &&
        (v.mode === "invasion" || v.mode === "coronation") &&
        isArrOf(v.steps, (s) => isRec(s) && typeof s.name === "string") &&
        isIntArr(v.winners),
    );
  }
  return raw as unknown as KidView;
}
