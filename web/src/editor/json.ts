/** Scenario JSON <-> editor model (docs/SCENARIOS.md section 1). Mirrors the structural checks of scenario.py. */
import {
  CARDS,
  FACTIONS,
  REGIONS,
  emptyCounts,
  emptyRegionCounts,
  fullHand,
  type Card,
  type Counts,
  type Faction,
  type LastCard,
  type Region,
  type RegionCounts,
  type RegionState,
  type RegionStates,
  type ReferenceBoard,
  type ScenarioModel,
} from "./model";

export class ScenarioParseError extends Error {
  constructor(
    message: string,
    public readonly path: string,
  ) {
    super(`${path}: ${message}`);
    this.name = "ScenarioParseError";
  }
}

const COMMON_KEYS = ["format", "kind", "description", "players", "slots", "regions", "courts", "example"];
const STATE_KEYS = [
  ...COMMON_KEYS,
  "to_play",
  "struggles",
  "region_state",
  "negotiation",
  "hands",
  "pass_count",
  "last_play",
  "hand_empty",
  "last_card",
];

type Obj = Record<string, unknown>;
const isObj = (x: unknown): x is Obj => typeof x === "object" && x !== null && !Array.isArray(x);
const bad = (path: string, msg: string): never => {
  throw new ScenarioParseError(msg, path);
};

function region(x: unknown, path: string): Region {
  return (REGIONS as readonly unknown[]).includes(x) ? (x as Region) : bad(path, `unknown region ${JSON.stringify(x)}`);
}

function nonNegInt(x: unknown, path: string): number {
  return typeof x === "number" && Number.isInteger(x) && x >= 0 ? x : bad(path, `bad count ${JSON.stringify(x)}`);
}

function counts(x: unknown, path: string): Counts {
  if (!isObj(x)) return bad(path, "count map expected");
  const out = emptyCounts();
  for (const [k, v] of Object.entries(x)) {
    if (!(FACTIONS as readonly string[]).includes(k)) bad(path, `unknown faction key ${JSON.stringify(k)}`);
    out[k as Faction] = nonNegInt(v, `${path}.${k}`);
  }
  return out;
}

function regionMap(x: unknown, path: string): RegionCounts {
  if (!isObj(x)) return bad(path, "map expected");
  const out = emptyRegionCounts();
  for (const [name, cm] of Object.entries(x)) out[region(name, path)] = counts(cm, `${path}.${name}`);
  return out;
}

function stateMap(x: unknown, path: string): RegionStates {
  if (!isObj(x)) return bad(path, "map expected");
  const out: RegionStates = {};
  for (const [name, v] of Object.entries(x)) {
    if (v !== "unstable" && !(FACTIONS as readonly unknown[]).includes(v)) bad(`${path}.${name}`, `bad region state ${JSON.stringify(v)}`);
    out[region(name, path)] = v as RegionState;
  }
  return out;
}

function perPlayer<T>(data: Obj, key: string, n: number, parse: (x: unknown, p: string) => T, dflt: () => T): T[] {
  if (!(key in data)) return Array.from({ length: n }, dflt);
  const v = data[key];
  if (!Array.isArray(v) || v.length !== n) return bad(key, `list of ${n} entries expected`);
  return v.map((x, i) => parse(x, `${key}[${i}]`));
}

const nullableInt = (x: unknown, p: string): number | null =>
  x === null ? null : typeof x === "number" && Number.isInteger(x) ? x : bad(p, "integer or null expected");

function card(x: unknown, path: string): Card {
  return (CARDS as readonly unknown[]).includes(x) ? (x as Card) : bad(path, `unknown card ${JSON.stringify(x)}`);
}

function lastCard(x: unknown): LastCard | null {
  if (x === null || x === undefined) return null;
  if (!isObj(x)) return bad("last_card", "object or null expected");
  const type = card(x.type, "last_card.type");
  let referenceBoard: ReferenceBoard | null = null;
  if ("reference_board" in x) {
    const rb = x.reference_board;
    if (!isObj(rb)) return bad("last_card.reference_board", "object expected");
    referenceBoard = {
      regions: regionMap(rb.regions ?? {}, "last_card.reference_board.regions"),
      regionState: stateMap(rb.region_state ?? {}, "last_card.reference_board.region_state"),
    };
  }
  return { type, referenceBoard };
}

/** Parse scenario JSON into a model (defaults filled in). Throws ScenarioParseError on malformed structure. */
export function fromScenarioJson(json: unknown): ScenarioModel {
  if (!isObj(json)) return bad("$", "scenario must be an object");
  if (json.format !== 1) bad("format", "format must be 1");
  const kind = json.kind;
  if (kind !== "setup" && kind !== "state") return bad("kind", `bad kind ${JSON.stringify(kind)}`);
  const allowed = kind === "setup" ? COMMON_KEYS : STATE_KEYS;
  const unknown = Object.keys(json).filter((k) => !allowed.includes(k));
  if (unknown.length) bad("$", `unknown keys ${JSON.stringify(unknown.sort())}`);
  const n = json.players;
  if (n !== 2 && n !== 3) return bad("players", `players must be 2 or 3, got ${JSON.stringify(n)}`);
  if (json.description !== undefined && typeof json.description !== "string") bad("description", "string expected");

  const names = json.slots;
  if (!Array.isArray(names) || names.length !== REGIONS.length) return bad("slots", "8 region names expected");
  const slots = names.map((x, i) => region(x, `slots[${i}]`));
  if (new Set(slots).size !== REGIONS.length) bad("slots", "slots must be a permutation of the 8 regions");
  if (!("courts" in json)) bad("courts", "courts required");

  const m: ScenarioModel = {
    kind,
    description: (json.description as string | undefined) ?? "",
    players: n,
    slots,
    regions: regionMap(json.regions ?? {}, "regions"),
    courts: perPlayer(json, "courts", n, counts, emptyCounts),
    toPlay: 0,
    struggles: 0,
    regionState: {},
    negotiation: Array<Region | null>(n).fill(null),
    hands: Array.from({ length: n }, fullHand),
    passCount: 0,
    lastPlay: Array<number | null>(n).fill(null),
    handEmpty: Array<number | null>(n).fill(null),
    lastCard: null,
    example: json.example,
  };
  if (kind === "state") {
    m.toPlay = "to_play" in json ? nonNegInt(json.to_play, "to_play") : 0;
    m.struggles = "struggles" in json ? nonNegInt(json.struggles, "struggles") : 0;
    m.regionState = stateMap(json.region_state ?? {}, "region_state");
    m.negotiation = perPlayer(json, "negotiation", n, (x, p) => (x === null ? null : region(x, p)), () => null);
    m.hands = perPlayer(
      json,
      "hands",
      n,
      (x, p) => (Array.isArray(x) ? x.map((c, i) => card(c, `${p}[${i}]`)) : bad(p, "list expected")),
      fullHand,
    );
    m.passCount = "pass_count" in json ? nonNegInt(json.pass_count, "pass_count") : 0;
    m.lastPlay = perPlayer(json, "last_play", n, nullableInt, () => null);
    m.handEmpty = perPlayer(json, "hand_empty", n, nullableInt, () => null);
    m.lastCard = lastCard(json.last_card);
  }
  return m;
}

function countsJson(c: Counts): Record<string, number> {
  const out: Record<string, number> = {};
  for (const f of FACTIONS) if (c[f] > 0) out[f] = c[f];
  return out;
}

function regionsJson(r: RegionCounts): Record<string, Record<string, number>> {
  const out: Record<string, Record<string, number>> = {};
  for (const name of REGIONS) {
    const c = countsJson(r[name]);
    if (Object.keys(c).length) out[name] = c;
  }
  return out;
}

function statesJson(s: RegionStates): Record<string, string> {
  const out: Record<string, string> = {};
  for (const name of REGIONS) if (s[name] !== undefined) out[name] = s[name];
  return out;
}

/** Serialise a model. Zero counts and empty regions are omitted; setup models emit setup keys only. */
export function toScenarioJson(m: ScenarioModel): Record<string, unknown> {
  const out: Record<string, unknown> = { format: 1, kind: m.kind };
  if (m.description !== "") out.description = m.description;
  out.players = m.players;
  out.slots = [...m.slots];
  out.regions = regionsJson(m.regions);
  out.courts = m.courts.map(countsJson);
  if (m.kind === "state") {
    out.to_play = m.toPlay;
    out.struggles = m.struggles;
    out.region_state = statesJson(m.regionState);
    out.negotiation = [...m.negotiation];
    out.hands = m.hands.map((h) => [...h]);
    out.pass_count = m.passCount;
    out.last_play = [...m.lastPlay];
    out.hand_empty = [...m.handEmpty];
    if (m.lastCard === null) out.last_card = null;
    else {
      const lc: Record<string, unknown> = { type: m.lastCard.type };
      if (m.lastCard.referenceBoard) {
        lc.reference_board = {
          regions: regionsJson(m.lastCard.referenceBoard.regions),
          region_state: statesJson(m.lastCard.referenceBoard.regionState),
        };
      }
      out.last_card = lc;
    }
  }
  if (m.example !== undefined) out.example = m.example;
  return out;
}
