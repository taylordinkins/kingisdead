import { useEffect, useMemo, useState, type ChangeEvent, type ReactNode } from "react";
import { api } from "../api/client";
import { Token, factionStyle } from "../games/king-is-dead/board/factions";
import type { SeatType } from "../shell/useGame";
import EditorMap from "./EditorMap";
import { EXAMPLES } from "./examples";
import { ScenarioParseError, fromScenarioJson, toScenarioJson } from "./json";
import {
  CARDS,
  CARDS_PER_HAND,
  FACTIONS,
  REGIONS,
  addCard,
  moveCard,
  newSetupModel,
  newStateModel,
  removeCard,
  setCourtFollowers,
  setDescription,
  setFollowers,
  setHandEmpty,
  setKind,
  setLastCard,
  setLastPlay,
  setNegotiation,
  setPassCount,
  setPlayers,
  setReferenceBoard,
  setRegionState,
  setStruggles,
  setToPlay,
  type Card,
  type Faction,
  type Kind,
  type Region,
  type RegionState,
  type ScenarioModel,
} from "./model";
import { serverValidate } from "./serverValidate";
import { summarize, validate, type Issue } from "./validate";

export const STORAGE_KEY = "kid.editor.model";

function loadStored(): ScenarioModel {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (raw) return fromScenarioJson(JSON.parse(raw));
  } catch {
    /* ignore corrupt or unavailable storage */
  }
  return newSetupModel(2);
}

const hits = (issues: Issue[], prefix: string): boolean =>
  issues.some((i) => i.fields.some((f) => f === prefix || f.startsWith(`${prefix}.`)));

const box = { border: "1px solid #8886", borderRadius: 6, padding: "6px 10px", margin: "8px 0" } as const;
const badBox = { ...box, border: "2px solid #c0392b" } as const;

function Stepper({ label, value, onChange, min = 0 }: { label: string; value: number; onChange: (n: number) => void; min?: number }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
      <button type="button" aria-label={`Decrease ${label}`} disabled={value <= min} onClick={() => onChange(value - 1)}>
        −
      </button>
      <span role="img" aria-label={label} style={{ minWidth: 22, textAlign: "center", fontWeight: 700 }}>
        {value}
      </span>
      <button type="button" aria-label={`Increase ${label}`} onClick={() => onChange(value + 1)}>
        +
      </button>
    </span>
  );
}

function FactionTag({ f }: { f: Faction }) {
  const i = FACTIONS.indexOf(f);
  return (
    <svg width="22" height="22" viewBox="-14 -14 28 28" aria-hidden="true" style={{ verticalAlign: "middle" }}>
      <Token faction={i} x={0} y={0} r={11} />
    </svg>
  );
}

function Section({ title, hint, bad, children, open }: { title: string; hint?: string; bad?: boolean; children: ReactNode; open?: boolean }) {
  return (
    <details open={open} style={bad ? badBox : box} data-bad={bad ? "true" : undefined}>
      <summary title={hint} style={{ cursor: "pointer", fontWeight: 600 }}>
        {title}
        {bad ? " (problem)" : ""}
      </summary>
      {hint && <p style={{ margin: "4px 0", opacity: 0.75, fontSize: "0.9em" }}>{hint}</p>}
      {children}
    </details>
  );
}

interface Props {
  onCreated: (gameId: string) => void;
  onExit: () => void;
}

export default function Editor({ onCreated, onExit }: Props) {
  const [model, setModel] = useState<ScenarioModel>(loadStored);
  const [selected, setSelected] = useState<Region>("Moray");
  const [importText, setImportText] = useState("");
  const [importError, setImportError] = useState<string | null>(null);
  const [seats, setSeats] = useState<SeatType[]>(["human", "human", "human"]);
  const [serverMsg, setServerMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(toScenarioJson(model)));
    } catch {
      /* storage unavailable */
    }
  }, [model]);

  const issues = useMemo(() => validate(model), [model]);
  const summary = useMemo(() => summarize(model), [model]);
  const json = useMemo(() => JSON.stringify(toScenarioJson(model), null, 2), [model]);
  const update = (fn: (m: ScenarioModel) => ScenarioModel) => {
    setModel(fn);
    setServerMsg(null);
  };
  const isState = model.kind === "state";
  const badRegions = new Set(REGIONS.filter((r) => hits(issues, `regions.${r}`) || hits(issues, `regionState.${r}`)));
  const valid = issues.length === 0;

  function changeKind(kind: Kind) {
    if (kind === model.kind) return;
    // Switching to state keeps the board; per-state fields already hold R-014 start values.
    update((m) => setKind(m, kind));
  }
  function reset() {
    update(() => (model.kind === "state" ? newStateModel(model.players) : newSetupModel(model.players)));
  }

  function load(raw: unknown) {
    try {
      setModel(fromScenarioJson(raw));
      setImportError(null);
      setServerMsg(null);
    } catch (ex) {
      setImportError(
        ex instanceof ScenarioParseError || ex instanceof Error ? ex.message : "Import failed",
      );
    }
  }
  function importPasted() {
    let raw: unknown;
    try {
      raw = JSON.parse(importText);
    } catch (ex) {
      setImportError(`Not valid JSON: ${ex instanceof Error ? ex.message : String(ex)}`);
      return;
    }
    load(raw);
  }
  async function importFile(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const text = await file.text();
      setImportText(text);
      load(JSON.parse(text));
    } catch (ex) {
      setImportError(`Not valid JSON: ${ex instanceof Error ? ex.message : String(ex)}`);
    }
  }
  function download() {
    const url = URL.createObjectURL(new Blob([json], { type: "application/json" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = "scenario.json";
    a.click();
    URL.revokeObjectURL(url);
  }
  async function copy() {
    try {
      await navigator.clipboard.writeText(json);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      setImportError("Clipboard unavailable; copy from the JSON preview instead.");
    }
  }

  async function check() {
    setBusy(true);
    try {
      const r = await serverValidate(model);
      setServerMsg(r.ok ? { ok: true, text: "Server accepts this scenario." } : { ok: false, text: r.detail ?? "Rejected" });
    } catch (ex) {
      setServerMsg({ ok: false, text: ex instanceof Error ? ex.message : "Network error" });
    } finally {
      setBusy(false);
    }
  }
  async function play() {
    setBusy(true);
    setServerMsg(null);
    try {
      const { data, error } = await api.POST("/api/games", {
        body: {
          game: "king_is_dead",
          params: { num_players: model.players },
          seats: seats.slice(0, model.players),
          scenario: toScenarioJson(model),
        },
      });
      if (data) onCreated(data.id);
      else {
        const detail = (error as { detail?: unknown } | undefined)?.detail;
        setServerMsg({ ok: false, text: typeof detail === "string" ? detail : JSON.stringify(detail ?? error) });
      }
    } catch (ex) {
      setServerMsg({ ok: false, text: ex instanceof Error ? ex.message : "Network error" });
    } finally {
      setBusy(false);
    }
  }

  const sel = model.regions[selected];
  const selState: RegionState | "" = model.regionState[selected] ?? "";

  return (
    <div className="kid-map" style={{ background: "transparent" }}>
      <h2>Setup editor</h2>
      <p>
        <button type="button" onClick={onExit}>
          Back to lobby
        </button>{" "}
        <button type="button" onClick={reset} title="Clear the board for the current kind and player count">
          Clear
        </button>
      </p>

      <fieldset style={box}>
        <legend>Table</legend>
        <label>
          Kind{" "}
          <select
            aria-label="Kind"
            value={model.kind}
            onChange={(e) => changeKind(e.target.value as Kind)}
            title="setup: a fresh position before the first move. state: a mid-game position with hands, struggles and so on."
          >
            <option value="setup">setup (fresh position)</option>
            <option value="state">state (mid-game)</option>
          </select>
        </label>{" "}
        <label>
          Players{" "}
          <select aria-label="Players" value={model.players} onChange={(e) => update((m) => setPlayers(m, Number(e.target.value) as 2 | 3))}>
            <option value={2}>2</option>
            <option value={3}>3</option>
          </select>
        </label>{" "}
        <label>
          Description{" "}
          <input aria-label="Description" value={model.description} onChange={(e) => update((m) => setDescription(m, e.target.value))} size={50} />
        </label>
      </fieldset>

      <div style={{ display: "flex", flexWrap: "wrap", gap: 16, alignItems: "flex-start" }}>
        <div style={{ flex: "1 1 460px" }}>
          <EditorMap model={model} selected={selected} onSelect={setSelected} bad={badRegions} />

          <fieldset style={badRegions.has(selected) ? badBox : box} aria-label={`Edit ${selected}`}>
            <legend>{selected} (click a region on the map)</legend>
            {FACTIONS.map((f) => (
              <div key={f}>
                <FactionTag f={f} /> {factionStyle(FACTIONS.indexOf(f)).letter}{" "}
                <Stepper label={`${f} in ${selected}`} value={sel[f]} onChange={(n) => update((m) => setFollowers(m, selected, f, n))} />
              </div>
            ))}
            {isState && (
              <label title="Closed region: held by a faction or unstable. Closed regions must be empty (V2).">
                Region state{" "}
                <select
                  aria-label={`State of ${selected}`}
                  value={selState}
                  onChange={(e) => update((m) => setRegionState(m, selected, e.target.value === "" ? undefined : (e.target.value as RegionState)))}
                >
                  <option value="">open</option>
                  <option value="S">held by S</option>
                  <option value="W">held by W</option>
                  <option value="E">held by E</option>
                  <option value="unstable">unstable</option>
                </select>
              </label>
            )}
          </fieldset>

          <Section
            title="Region card track"
            hint="Slot 1 is leftmost. Slots 1..struggles are face down in a state scenario. Use the arrows to reorder."
            open
            bad={hits(issues, "slots")}
          >
            <ol aria-label="Region card track" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(120px,1fr))", gap: 6, padding: 0, listStyle: "none" }}>
              {model.slots.map((r, i) => {
                const down = summary.faceDownSlots.includes(i + 1);
                return (
                  <li
                    key={r}
                    data-testid={`slot-${i + 1}`}
                    style={{
                      border: "2px solid var(--card-edge)",
                      borderRadius: 8,
                      padding: 6,
                      textAlign: "center",
                      background: down ? "var(--back)" : "var(--card)",
                      color: down ? "#f0e6cc" : "var(--ink)",
                    }}
                  >
                    <div>
                      <b>{i + 1}</b> {down ? "(face down)" : ""}
                    </div>
                    <div>{r}</div>
                    <button type="button" aria-label={`Move ${r} card earlier`} disabled={i === 0} onClick={() => update((m) => moveCard(m, i, i - 1))}>
                      ◀
                    </button>
                    <button type="button" aria-label={`Move ${r} card later`} disabled={i === model.slots.length - 1} onClick={() => update((m) => moveCard(m, i, i + 1))}>
                      ▶
                    </button>
                  </li>
                );
              })}
            </ol>
          </Section>

          <Section title="Courts" hint="Followers in each player's court. Each court must hold exactly 2 (V11)." open bad={hits(issues, "courts")}>
            {model.courts.map((c, p) => (
              <div key={p} style={hits(issues, `courts.${p}`) ? badBox : box} data-bad={hits(issues, `courts.${p}`) ? "true" : undefined}>
                <b>Player {p + 1} court</b> ({summary.courtTotals[p]})
                {FACTIONS.map((f) => (
                  <span key={f} style={{ marginLeft: 12 }}>
                    <FactionTag f={f} /> <Stepper label={`${f} in court ${p + 1}`} value={c[f]} onChange={(n) => update((m) => setCourtFollowers(m, p, f, n))} />
                  </span>
                ))}
              </div>
            ))}
          </Section>

          {isState && (
            <>
              <Section title="Hands" hint={`Cards left in each hand (at most ${CARDS_PER_HAND}). Played cards are the ones missing.`} bad={hits(issues, "hands")}>
                {model.hands.map((h, p) => (
                  <div key={p} style={hits(issues, `hands.${p}`) ? badBox : box} data-bad={hits(issues, `hands.${p}`) ? "true" : undefined}>
                    <b>Player {p + 1}</b>: {h.length} cards
                    <ul style={{ listStyle: "none", padding: 0 }}>
                      {CARDS.map((c: Card) => (
                        <li key={c}>
                          <Stepper
                            label={`${c.replace("_", " ")} in hand ${p + 1}`}
                            value={h.filter((x) => x === c).length}
                            onChange={(n) => update((m) => (n > h.filter((x) => x === c).length ? addCard(m, p, c) : removeCard(m, p, c)))}
                          />{" "}
                          {c.replace("_", " ")}
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </Section>

              <Section title="Turn state" hint="Whose turn it is, how many struggles are resolved, and passes so far." bad={hits(issues, "toPlay") || hits(issues, "struggles") || hits(issues, "passCount")}>
                <label title="Player whose turn it is (shown 1-based).">
                  To play{" "}
                  <select aria-label="To play" value={model.toPlay} onChange={(e) => update((m) => setToPlay(m, Number(e.target.value)))}>
                    {model.courts.map((_, p) => (
                      <option key={p} value={p}>
                        Player {p + 1}
                      </option>
                    ))}
                  </select>
                </label>{" "}
                <label title="Resolved struggles; region cards 1..N are face down (0..8).">
                  Struggles <Stepper label="Struggles" value={model.struggles} onChange={(n) => update((m) => setStruggles(m, Math.min(8, n)))} />
                </label>{" "}
                <label title="Consecutive passes so far; must be below the player count (V9).">
                  Passes <Stepper label="Passes" value={model.passCount} onChange={(n) => update((m) => setPassCount(m, n))} />
                </label>
              </Section>

              <Section title="Negotiation, last play, empty hands" hint="Per-player discs and history values." bad={hits(issues, "negotiation") || hits(issues, "lastPlay") || hits(issues, "handEmpty")}>
                {model.courts.map((_, p) => (
                  <div key={p}>
                    <b>Player {p + 1}</b>{" "}
                    <label title="Region where this player has a negotiation disc.">
                      Negotiation disc{" "}
                      <select
                        aria-label={`Negotiation disc ${p + 1}`}
                        value={model.negotiation[p] ?? ""}
                        onChange={(e) => update((m) => setNegotiation(m, p, e.target.value === "" ? null : (e.target.value as Region)))}
                      >
                        <option value="">none</option>
                        {REGIONS.map((r) => (
                          <option key={r}>{r}</option>
                        ))}
                      </select>
                    </label>{" "}
                    <NullableNumber
                      label={`Last play ${p + 1}`}
                      title="Index of the previous play in the history (blank = none)."
                      value={model.lastPlay[p] ?? null}
                      onChange={(v) => update((m) => setLastPlay(m, p, v))}
                    />{" "}
                    <NullableNumber
                      label={`Hand empty ${p + 1}`}
                      title="Time the hand became empty (blank = not empty)."
                      value={model.handEmpty[p] ?? null}
                      onChange={(v) => update((m) => setHandEmpty(m, p, v))}
                    />
                  </div>
                ))}
              </Section>

              <Section title="Last card played" hint="The previous card, needed for the Outmanoeuvre/Manoeuvre repeat-board rule." bad={hits(issues, "lastCard")}>
                <label>
                  Last card{" "}
                  <select
                    aria-label="Last card"
                    value={model.lastCard?.type ?? ""}
                    onChange={(e) =>
                      update((m) => setLastCard(m, e.target.value === "" ? null : { type: e.target.value as Card, referenceBoard: m.lastCard?.referenceBoard ?? null }))
                    }
                  >
                    <option value="">none</option>
                    {CARDS.map((c) => (
                      <option key={c} value={c}>
                        {c.replace("_", " ")}
                      </option>
                    ))}
                  </select>
                </label>
                {model.lastCard && (
                  <label style={{ marginLeft: 12 }} title="Board B* before the last (out)manoeuvre. Omitted means void.">
                    <input
                      type="checkbox"
                      checked={model.lastCard.referenceBoard !== null}
                      onChange={(e) =>
                        update((m) => setReferenceBoard(m, e.target.checked ? { regions: structuredClone(m.regions), regionState: { ...m.regionState } } : null))
                      }
                    />{" "}
                    Include reference board (copies the current board; edit details via JSON import)
                  </label>
                )}
              </Section>
            </>
          )}
        </div>

        <div style={{ flex: "1 1 300px" }}>
          <Section title="Supply" hint="Followers of each faction left in the pool after the board and courts." open>
            {FACTIONS.map((f) => (
              <div key={f} data-testid={`supply-${f}`}>
                <FactionTag f={f} /> {f}: {summary.supply[f]} left of {summary.pool} ({summary.onBoard[f]} on board, {summary.inCourts[f]} in courts)
              </div>
            ))}
            {isState && (
              <div>
                Cards played: {summary.cardPlays}; unstable discs: {summary.unstableDiscs}
              </div>
            )}
          </Section>

          <section aria-label="Validation" style={valid ? { ...box, border: "2px solid #2e8b57" } : badBox}>
            <h3 style={{ margin: 0 }}>Validation</h3>
            {valid ? (
              <p role="status">Valid: this scenario passes V1..V11.</p>
            ) : (
              <ul aria-label="Issues">
                {issues.map((i, n) => (
                  <li key={n}>
                    <b>{i.code}</b> {i.message}
                  </li>
                ))}
              </ul>
            )}
          </section>

          <fieldset style={box}>
            <legend>Play</legend>
            {model.courts.map((_, p) => (
              <div key={p}>
                <label>
                  Seat {p + 1}{" "}
                  <select aria-label={`Seat ${p + 1}`} value={seats[p]} onChange={(e) => setSeats(seats.map((x, j) => (j === p ? (e.target.value as SeatType) : x)))}>
                    <option value="human">human</option>
                    <option value="random">random</option>
                  </select>
                </label>
              </div>
            ))}
            <button type="button" disabled={!valid || busy} onClick={() => void check()}>
              Check with server
            </button>{" "}
            <button type="button" disabled={!valid || busy} onClick={() => void play()}>
              Start playing
            </button>
            {serverMsg && <p role={serverMsg.ok ? "status" : "alert"}>{serverMsg.ok ? serverMsg.text : `Server: ${serverMsg.text}`}</p>}
          </fieldset>

          <Section title="Import / export" open>
            <label>
              Load example{" "}
              <select
                aria-label="Load example"
                value=""
                onChange={(e) => {
                  const ex = EXAMPLES[Number(e.target.value)];
                  if (ex) load(ex.json);
                }}
              >
                <option value="">choose...</option>
                {EXAMPLES.map((ex, i) => (
                  <option key={ex.name} value={i}>
                    {ex.name}
                  </option>
                ))}
              </select>
            </label>
            <div>
              <textarea aria-label="Paste JSON" rows={5} style={{ width: "100%" }} value={importText} onChange={(e) => setImportText(e.target.value)} />
              <button type="button" onClick={importPasted} disabled={importText.trim() === ""}>
                Import JSON
              </button>{" "}
              <label>
                or file <input type="file" accept="application/json,.json" aria-label="Import file" onChange={(e) => void importFile(e)} />
              </label>
              {importError && <p role="alert">Import error: {importError}</p>}
            </div>
            <div>
              <button type="button" onClick={download}>
                Download JSON
              </button>{" "}
              <button type="button" onClick={() => void copy()}>
                {copied ? "Copied" : "Copy JSON"}
              </button>
            </div>
            <details>
              <summary>JSON preview</summary>
              <textarea aria-label="Scenario JSON" readOnly rows={12} style={{ width: "100%" }} value={json} />
            </details>
          </Section>
        </div>
      </div>
    </div>
  );
}

function NullableNumber({ label, title, value, onChange }: { label: string; title: string; value: number | null; onChange: (v: number | null) => void }) {
  return (
    <label title={title}>
      {label.replace(/ \d+$/, "")}{" "}
      <input
        aria-label={label}
        type="number"
        min={0}
        style={{ width: 60 }}
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value === "" ? null : Math.max(0, Math.trunc(Number(e.target.value))))}
      />
    </label>
  );
}
