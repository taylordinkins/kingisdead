import { useState, type ReactNode } from "react";
import type { GameView, LegalAction } from "../../shell/useGame";
import { MapBoard, VIEW_H } from "./board/MapBoard";
import { REGION_SHAPES } from "./board/geometry";
import { factionStyle } from "./board/factions";
import { Players } from "./board/Players";
import { parseKidView, type KidView, type ScoringStep } from "./types";

type Fname = (f: number | null) => string;
const player = (p: number | null): string => (p === null ? "none" : `P${p}`);
const list = (xs: number[] | undefined): string =>
  xs && xs.length ? xs.map(player).join(", ") : "none";
const words = (s: string): string => s.replace(/_/g, " ");

function ScoringStepRow({ step, fname }: { step: ScoringStep; fname: Fname }) {
  return (
    <tr>
      <th scope="row">{words(step.name)}</th>
      {step.skipped ? (
        <td colSpan={3}>skipped</td>
      ) : (
        <>
          <td>{step.faction === null ? "-" : fname(step.faction)}</td>
          <td>{(step.values ?? []).map((v, p) => `${player(p)}: ${v ?? "-"}`).join(", ")}</td>
          <td>{list(step.remaining)}</td>
        </>
      )}
    </tr>
  );
}

function Header({ v, fname, cardName }: { v: KidView; fname: Fname; cardName: (id: string) => string }): ReactNode {
  const region = (r: number): string => v.regions[r]?.name ?? String(r);
  const p = v.pending;
  return (
    <dl aria-label="Turn status">
      <dt>Stage</dt>
      <dd>{words(v.stage)}</dd>
      <dt>Phase</dt>
      <dd>{words(v.phase)}</dd>
      <dt>Current player</dt>
      <dd>
        {v.is_terminal ? "game over" : v.current_player === null ? "chance" : player(v.current_player)}
      </dd>
      <dt>Consecutive passes</dt>
      <dd>{v.consecutive_passes}</dd>
      {p.card != null && (
        <>
          <dt>Pending card</dt>
          <dd>{cardName(String(p.card))}</dd>
        </>
      )}
      {p.assemble_faction != null && (
        <>
          <dt>Assembling</dt>
          <dd>{fname(p.assemble_faction)}</dd>
        </>
      )}
      {p.neg_first != null && (
        <>
          <dt>Negotiation first region</dt>
          <dd>{region(p.neg_first)}</dd>
        </>
      )}
      {p.neg_second != null && (
        <>
          <dt>Negotiation second region</dt>
          <dd>{region(p.neg_second)}</dd>
        </>
      )}
    </dl>
  );
}

export interface ClickToAct {
  /** Legal actions the viewer may submit right now (empty/absent when not their turn). */
  actions: LegalAction[];
  onAct: (actionId: number) => void;
  labelFor?: (a: LegalAction) => string;
}

function RegionChooser({
  v,
  region,
  actions,
  labelFor,
  onPick,
  onClose,
}: {
  v: KidView;
  region: number;
  actions: LegalAction[];
  labelFor: (a: LegalAction) => string;
  onPick: (id: number) => void;
  onClose: () => void;
}) {
  const shape = REGION_SHAPES[region];
  const name = v.regions[region]?.name ?? `Region ${region}`;
  const [cx, cy] = shape ? shape.centre : [500, 300];
  return (
    <div
      role="group"
      aria-label={`Choose an action in ${name}`}
      data-testid="region-chooser"
      onKeyDown={(e) => {
        if (e.key === "Escape") onClose();
      }}
      style={{
        position: "absolute",
        left: `${Math.min(Math.max((cx / 1000) * 100, 12), 88)}%`,
        top: `${(cy / VIEW_H) * 100}%`,
        transform: "translate(-50%, 0)",
        display: "flex",
        flexWrap: "wrap",
        gap: 4,
        justifyContent: "center",
        padding: 6,
        borderRadius: 10,
        background: "var(--card, #f7efdc)",
        border: "2px solid #d99a00",
        boxShadow: "0 3px 10px rgba(0,0,0,.4)",
        zIndex: 5,
      }}
    >
      {actions.map((a) => {
        const st = a.faction != null ? factionStyle(a.faction) : null;
        return (
          <button
            type="button"
            key={a.id}
            autoFocus={a === actions[0]}
            onClick={() => onPick(a.id)}
            style={{
              background: st?.fill,
              color: st?.ink,
              border: `2px solid ${st?.stroke ?? "#444"}`,
              borderRadius: 8,
              padding: "4px 8px",
              cursor: "pointer",
              font: "inherit",
            }}
          >
            {labelFor(a)}
          </button>
        );
      })}
      <button type="button" onClick={onClose} aria-label="Cancel choice">
        ×
      </button>
    </div>
  );
}

export function KidBoard({
  v,
  legalRegions,
  hoverRegionFromAction = null,
  click,
}: {
  click?: ClickToAct;
  v: KidView;
  /** Regions targeted by the legal actions available to the viewer. */
  legalRegions?: ReadonlySet<number>;
  hoverRegionFromAction?: number | null;
}) {
  const [cardHover, setCardHover] = useState<number | null>(null);
  const [choosing, setChoosing] = useState<number | null>(null);
  const clickable = click?.actions ?? [];
  const labelFor = (a: LegalAction): string => click?.labelFor?.(a) ?? a.label;
  const byRegion = new Map<number, LegalAction[]>();
  const playable = new Map<string, { id: number; label: string }>();
  for (const a of clickable) {
    if ((a.kind === "region" || a.kind === "follower") && a.region != null) {
      byRegion.set(a.region, [...(byRegion.get(a.region) ?? []), a]);
    } else if (a.kind === "play" && a.card != null) {
      playable.set(String(a.card), { id: a.id, label: labelFor(a) });
    }
  }
  const submit = (id: number) => {
    setChoosing(null);
    click?.onAct(id);
  };
  const onRegionClick = (r: number) => {
    const as = byRegion.get(r) ?? [];
    if (as.length === 1) submit(as[0]!.id);
    else if (as.length > 1) setChoosing(r);
  };
  const regionLabel = (r: number): string | undefined => {
    const as = byRegion.get(r);
    if (!as) return undefined;
    return as.length === 1 ? labelFor(as[0]!) : `Choose an action in ${v.regions[r]?.name ?? r}`;
  };
  const chooserActions = choosing === null ? [] : (byRegion.get(choosing) ?? []);
  const hover = cardHover ?? hoverRegionFromAction;
  const fname: Fname = (f) =>
    f === null ? "none" : (v.faction_names[f] ?? `Faction ${f}`);
  const cardName = (id: string): string => v.card_names[id] ?? `Card ${id}`;
  const factions = v.faction_names;
  const regionName = (r: number | null): string =>
    r === null ? "(not placed)" : (v.regions[r]?.name ?? `Region ${r}`);
  const sc = v.scoring;
  return (
    <div aria-label="King is Dead board">
      <p>
        Regions resolved: {v.struggles_resolved} of {v.track.length}
      </p>
      <div style={{ position: "relative" }}>
        <MapBoard
          v={v}
          highlightRegions={legalRegions}
          hoverRegion={hover}
          onHoverRegion={setCardHover}
          onRegionClick={click ? onRegionClick : undefined}
          clickableRegions={new Set(byRegion.keys())}
          regionActionLabel={regionLabel}
        />
        {choosing !== null && chooserActions.length > 1 && (
          <RegionChooser
            v={v}
            region={choosing}
            actions={chooserActions}
            labelFor={labelFor}
            onPick={submit}
            onClose={() => setChoosing(null)}
          />
        )}
      </div>
      <Players
        v={v}
        playable={playable}
        playableSeat={v.current_player}
        onPlayCard={click ? submit : undefined}
      />
      <Header v={v} fname={fname} cardName={cardName} />

      <h3>Power struggle track</h3>
      <table aria-label="Region track">
        <thead>
          <tr>
            <th scope="col">Slot</th>
            <th scope="col">Region</th>
            <th scope="col">Status</th>
            <th scope="col">Negotiation discs</th>
          </tr>
        </thead>
        <tbody>
          {v.track.map((t) => (
            <tr key={t.slot}>
              <th scope="row">{t.slot + 1}</th>
              <td>{regionName(t.region)}</td>
              <td>{t.face_down ? "resolved" : "pending"}</td>
              <td>{list(t.discs)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3>Regions</h3>
      <table aria-label="Regions">
        <thead>
          <tr>
            <th scope="col">Region</th>
            {factions.map((f) => (
              <th scope="col" key={f}>
                {f}
              </th>
            ))}
            <th scope="col">State</th>
            <th scope="col">Controller</th>
          </tr>
        </thead>
        <tbody>
          {v.regions.map((r) => (
            <tr key={r.region}>
              <th scope="row">{r.name}</th>
              {factions.map((f, i) => (
                <td key={f}>{r.followers[i] ?? 0}</td>
              ))}
              <td>{r.state}</td>
              <td>{r.state === "controlled" ? fname(r.controller) : "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {v.is_terminal && (
        <section aria-label="Result">
          <h3>Result</h3>
          {v.winners && <p>Winner(s): {list(v.winners)}</p>}
          {v.returns && (
            <table aria-label="Scores">
              <thead>
                <tr>
                  <th scope="col">Player</th>
                  <th scope="col">Score</th>
                </tr>
              </thead>
              <tbody>
                {v.returns.map((r, p) => (
                  <tr key={p}>
                    <th scope="row">{player(p)}</th>
                    <td>{r}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {sc && (
            <>
              <h4>Scoring breakdown ({sc.mode})</h4>
              {sc.faction_ranking && (
                <p>Faction ranking: {sc.faction_ranking.map(fname).join(" > ")}</p>
              )}
              {sc.regions_controlled && (
                <p>
                  Regions controlled:{" "}
                  {sc.regions_controlled.map((n, f) => `${fname(f)} ${n}`).join(", ")}
                </p>
              )}
              {sc.recent_win && (
                <>
                  <p>
                    Recent win:{" "}
                    {sc.recent_win
                      .map((n, f) => `${fname(f)} ${n < 0 ? "never" : `struggle ${n}`}`)
                      .join(", ")}
                  </p>
                  <p>
                    <small>
                      Recent win = the number of the power struggle in which a faction most
                      recently took control; never = no win. Breaks ties between factions
                      controlling equal numbers of regions (higher ranks first).
                    </small>
                  </p>
                </>
              )}
              <table aria-label="Scoring steps">
                <thead>
                  <tr>
                    <th scope="col">Step</th>
                    <th scope="col">Faction</th>
                    <th scope="col">Values</th>
                    <th scope="col">Remaining</th>
                  </tr>
                </thead>
                <tbody>
                  {sc.steps.map((s, i) => (
                    <ScoringStepRow key={i} step={s} fname={fname} />
                  ))}
                </tbody>
              </table>
            </>
          )}
        </section>
      )}
    </div>
  );
}

export default function Board({
  game,
  hoverAction = null,
  canAct = false,
  onAct,
  labelFor,
}: {
  game: GameView;
  hoverAction?: number | null;
  canAct?: boolean;
  onAct?: (actionId: number) => void;
  labelFor?: (a: LegalAction) => string;
}) {
  let v: KidView;
  try {
    v = parseKidView(game.view);
  } catch (e) {
    return (
      <p role="alert">Cannot display board: {e instanceof Error ? e.message : "invalid view"}</p>
    );
  }
  const humanTurn =
    !game.is_terminal && game.current_player !== null && game.seats[game.current_player] === "human";
  const regionActions = (humanTurn ? game.legal_actions : []).filter(
    (a) => (a.kind === "region" || a.kind === "follower") && a.region != null,
  );
  const legalRegions = new Set(regionActions.map((a) => a.region as number));
  const hovered = regionActions.find((a) => a.id === hoverAction)?.region ?? null;
  const click: ClickToAct | undefined =
    humanTurn && canAct && onAct ? { actions: game.legal_actions, onAct, labelFor } : undefined;
  return (
    <KidBoard v={v} legalRegions={legalRegions} hoverRegionFromAction={hovered} click={click} />
  );
}
