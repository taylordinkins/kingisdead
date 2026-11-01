import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import {
  addCard,
  fromScenarioJson,
  moveCard,
  newSetupModel,
  newStateModel,
  removeCard,
  ScenarioParseError,
  setCourtFollowers,
  setFollowers,
  setHand,
  setLastCard,
  setLastPlay,
  setNegotiation,
  setPlayers,
  setRegionState,
  setStruggles,
  summarize,
  swapCards,
  toScenarioJson,
  validate,
  type Card,
  type IssueCode,
  type ScenarioModel,
} from "./index";

const DIR = join(process.cwd(), "..", "tests", "scenarios");
const files = readdirSync(DIR).filter((f) => f.endsWith(".json"));
const load = (f: string): unknown => JSON.parse(readFileSync(join(DIR, f), "utf8"));
const codes = (m: ScenarioModel): IssueCode[] => [...new Set(validate(m).map((i) => i.code))];

/** A valid 2-player setup: every region 4 followers, homes >= 2, courts of 2. */
function validSetup(): ScenarioModel {
  let m = newSetupModel(2);
  const fill: Record<string, [number, number, number]> = {
    Moray: [2, 1, 1],
    Strathclyde: [1, 2, 1],
    Lancaster: [1, 1, 2],
    Northumbria: [2, 1, 1],
    Gwynedd: [1, 2, 1],
    Warwick: [1, 1, 2],
    Essex: [1, 1, 2],
    Devon: [1, 1, 2],
  };
  for (const [r, [s, w, e]] of Object.entries(fill)) {
    m = setFollowers(m, r as never, "S", s);
    m = setFollowers(m, r as never, "W", w);
    m = setFollowers(m, r as never, "E", e);
  }
  m = setCourtFollowers(m, 0, "S", 1);
  m = setCourtFollowers(m, 0, "W", 1);
  m = setCourtFollowers(m, 1, "E", 2);
  return m;
}

describe("scenario files", () => {
  it("finds scenarios", () => expect(files.length).toBeGreaterThanOrEqual(4));
  it.each(files)("%s round-trips and validates with zero issues (none fail in Python either)", (f) => {
    const json = load(f);
    const m = fromScenarioJson(json);
    expect(validate(m)).toEqual([]);
    const out = toScenarioJson(m);
    expect(fromScenarioJson(out)).toEqual(m);
    // every key written in the source file survives with the same meaning
    const src = json as Record<string, unknown>;
    for (const k of ["format", "kind", "players", "slots", "example", "hands", "last_play", "to_play"]) {
      if (k in src) expect(out[k]).toEqual(src[k]);
    }
    expect(out.courts).toEqual((src.courts as object[]).map((c) => Object.fromEntries(Object.entries(c).filter(([, v]) => (v as number) > 0))));
  });
});

describe("blank models", () => {
  it("2 and 3 player defaults", () => {
    const a = newStateModel(2);
    expect(a.courts).toHaveLength(2);
    expect(a.hands[0]).toHaveLength(8);
    expect(validate(a)).toEqual([]);
    expect(summarize(a).supply).toEqual({ S: 16, W: 16, E: 16 });
    expect(summarize(newStateModel(3)).supply).toEqual({ S: 18, W: 18, E: 18 });
    expect(newSetupModel(3).courts).toHaveLength(3);
    expect(codes(newSetupModel(2))).toEqual(["V11"]);
  });
  it("setup JSON omits state keys and round-trips", () => {
    const m = validSetup();
    expect(validate(m)).toEqual([]);
    const j = toScenarioJson(m);
    expect(Object.keys(j).sort()).toEqual(["courts", "format", "kind", "players", "regions", "slots"]);
    expect(fromScenarioJson(j)).toEqual(m);
  });
});

describe("mutations are pure", () => {
  it("setFollowers / moveCard / swapCards / setPlayers", () => {
    const m = newStateModel(2);
    const m2 = setFollowers(m, "Moray", "S", 3);
    expect(m.regions.Moray.S).toBe(0);
    expect(m2.regions.Moray.S).toBe(3);
    expect(setFollowers(m, "Moray", "S", -2).regions.Moray.S).toBe(0);
    expect(moveCard(m, 0, 7).slots[7]).toBe("Moray");
    expect(m.slots[0]).toBe("Moray");
    expect(swapCards(m, 0, 1).slots.slice(0, 2)).toEqual(["Strathclyde", "Moray"]);
    expect(new Set(moveCard(m, 2, 5).slots).size).toBe(8);
    const m3 = setPlayers(m, 3);
    expect(m3.courts).toHaveLength(3);
    expect(m3.hands[2]).toHaveLength(8);
    expect(setPlayers(m3, 2).hands).toHaveLength(2);
  });
  it("cards", () => {
    const m = newStateModel(2);
    const r = removeCard(m, 0, "negotiate");
    expect(r.hands[0]).toHaveLength(7);
    expect(m.hands[0]).toHaveLength(8);
    expect(addCard(r, 0, "negotiate").hands[0]).toHaveLength(8);
    expect(removeCard(removeCard(m, 0, "assemble"), 0, "assemble").hands[0]).toHaveLength(6);
  });
});

describe("parse errors", () => {
  const base = () => load("setup_basic.json") as Record<string, unknown>;
  it.each([
    ["bad format", { format: 2 }],
    ["unknown key", { to_play: 0 }],
    ["players", { players: 4 }],
    ["slots", { slots: ["Moray"] }],
    ["unknown region", { regions: { Atlantis: { S: 1 } } }],
    ["unknown faction", { courts: [{ X: 1 }, {}] }],
  ])("%s throws", (_n, patch) => {
    expect(() => fromScenarioJson({ ...base(), ...patch })).toThrow(ScenarioParseError);
  });
});

describe("validate: each rule fails and passes", () => {
  it("V1", () => {
    let m = newStateModel(2);
    expect(codes(m)).toEqual([]);
    m = setFollowers(m, "Moray", "S", 16);
    expect(codes(m)).toEqual([]);
    m = setCourtFollowers(m, 0, "S", 1);
    expect(codes(m)).toEqual(["V1"]);
    expect(codes(setPlayers(m, 3))).toEqual([]); // pool 18 with 3 players
  });
  it("V2", () => {
    let m = setStruggles(newStateModel(2), 1);
    m = setRegionState(m, "Moray", "S");
    expect(codes(m)).toEqual([]);
    expect(codes(setFollowers(m, "Moray", "W", 1))).toEqual(["V2"]);
  });
  it("V3", () => {
    let m = newStateModel(3);
    m = setStruggles(m, 2);
    m = setRegionState(m, "Moray", "unstable");
    m = setRegionState(m, "Strathclyde", "unstable");
    expect(codes(m)).toEqual([]);
    // 3 unstable, struggles 3, slot 3 (Lancaster) unstable: terminal by invasion, ok
    const t = setRegionState(setStruggles(setRegionState(m, "Lancaster", "unstable"), 3), "Devon", undefined);
    expect(codes(t)).toEqual([]);
    // 3 unstable but slot `struggles` is not one of them
    const bad = setStruggles(setRegionState(m, "Lancaster", "unstable"), 3);
    expect(codes(setRegionState(setRegionState(bad, "Lancaster", undefined), "Northumbria", "unstable"))).toContain("V3");
    // 4 unstable
    expect(codes(setRegionState(setStruggles(setRegionState(t, "Northumbria", "unstable"), 4), "Devon", undefined))).toContain("V3");
  });
  it("V4", () => {
    let m = setRegionState(newStateModel(2), "Moray", "S");
    expect(codes(m)).toEqual(["V4"]); // struggles 0 but one closed
    m = setStruggles(m, 1);
    expect(codes(m)).toEqual([]);
    expect(codes(setRegionState(setRegionState(m, "Moray", undefined), "Devon", "S"))).toEqual(["V4"]);
  });
  it("V6", () => {
    let m = removeCard(newStateModel(2), 0, "negotiate");
    m = removeCard(m, 1, "negotiate");
    m = setLastPlay(setLastPlay(m, 0, 1), 1, 2);
    m = setLastCard({ ...m, hands: m.hands }, { type: "negotiate", referenceBoard: null });
    m = setNegotiation(m, 0, "Moray");
    m = setNegotiation(m, 1, "Devon");
    expect(codes(m)).toEqual([]);
    expect(codes(setNegotiation(m, 1, "Moray"))).toEqual(["V6"]);
    expect(codes(setNegotiation(newStateModel(2), 0, "Moray"))).toContain("V6"); // still holds negotiate
  });
  it("V7", () => {
    let m = removeCard(newStateModel(2), 0, "manoeuvre");
    m = setLastCard(m, { type: "manoeuvre", referenceBoard: null });
    expect(codes(m)).toContain("V7"); // last_play missing
    m = setLastPlay(m, 0, 1);
    expect(codes(m)).toEqual([]);
    expect(codes(setLastPlay(m, 0, 2))).toContain("V7"); // exceeds total
    // empty hand needs hand_empty == last_play
    let e = setHand(newStateModel(2), 0, []);
    e = setHand(e, 1, newStateModel(2).hands[1] as Card[]);
    expect(codes(e)).toContain("V7");
  });
  it("V8", () => {
    const m = newStateModel(2);
    expect(codes(m)).toEqual([]);
    expect(codes(addCard(m, 0, "assemble"))).toContain("V8");
  });
  it("V9", () => {
    const m = newStateModel(2);
    expect(codes({ ...m, passCount: 1 })).toEqual([]);
    expect(codes({ ...m, passCount: 2 })).toEqual(["V9"]);
  });
  it("V10", () => {
    const m = newStateModel(2);
    expect(codes(setLastCard(m, { type: "assemble", referenceBoard: null }))).toContain("V10"); // no plays
    let p = setLastPlay(removeCard(m, 0, "assemble"), 0, 1);
    p = setLastCard(p, { type: "assemble", referenceBoard: null });
    expect(codes(p)).toEqual([]); // one copy left is fine
    expect(codes(setLastCard(p, { type: "manoeuvre", referenceBoard: null }))).toContain("V10"); // still held
    const rb = { regions: newStateModel(2).regions, regionState: {} };
    expect(codes(setLastCard(p, { type: "assemble", referenceBoard: rb }))).toContain("V10");
    let q = setLastPlay(removeCard(m, 0, "outmanoeuvre"), 0, 1);
    q = setLastCard(q, { type: "outmanoeuvre", referenceBoard: rb });
    expect(codes(q)).toEqual([]);
    const over = { ...rb, regions: setFollowers(newStateModel(2), "Moray", "S", 17).regions };
    expect(codes(setLastCard(q, { type: "outmanoeuvre", referenceBoard: over }))).toEqual(["V1"]);
    const closed = { regions: setFollowers(newStateModel(2), "Moray", "S", 1).regions, regionState: { Moray: "W" as const } };
    expect(codes(setLastCard(q, { type: "outmanoeuvre", referenceBoard: closed }))).toEqual(["V2"]);
  });
  it("V11", () => {
    const m = validSetup();
    expect(validate(m)).toEqual([]);
    expect(codes(setFollowers(m, "Devon", "S", 2))).toContain("V11"); // 5 followers
    // Moray 1 Scottish (still 4 total)
    let h = setFollowers(setFollowers(m, "Moray", "S", 1), "Moray", "E", 2);
    expect(validate(h).map((i) => i.code)).toEqual(["V11"]);
    h = setCourtFollowers(m, 1, "E", 3);
    expect(codes(h)).toContain("V11");
  });
});

describe("summary", () => {
  it("derives supply, recent wins, face-down slots", () => {
    const m = fromScenarioJson(load("coronation_tiebreak.json"));
    const s = summarize(m);
    expect(s.faceDownSlots).toEqual([1, 2, 3, 4, 5, 6, 7, 8]);
    expect(s.unstableDiscs).toBe(1);
    expect(s.recentWin).toEqual({ S: 8, W: 7, E: 4 });
    expect(s.cardPlays).toBe(8 * 3 - 7);
    expect(s.supply.S).toBe(18 - 5);
    expect(s.pool).toBe(18);
  });
});
