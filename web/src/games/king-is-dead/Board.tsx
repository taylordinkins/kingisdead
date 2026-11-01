import { useState, type ReactNode } from "react";
import "./board/board.css";
import type { GameView, LegalAction } from "../../shell/useGame";
import { MapBoard, VIEW_H } from "./board/MapBoard";
import { REGION_SHAPES } from "./board/geometry";
import { factionStyle } from "./board/factions";
import { Players } from "./board/Players";
import ScoringPanel from "./ScoringPanel";
import { canonicalSequence, firstPicks, partnersOf } from "./swap";
import { parseKidView, type KidView } from "./types";

type Fname = (f: number | null) => string;
const player = (p: number | null): string => (p === null ? "none" : `P${p}`);
const list = (xs: number[] | undefined): string =>
  xs && xs.length ? xs.map(player).join(", ") : "none";
const words = (s: string): string => s.replace(/_/g, " ");


function Header({ v, fname, cardName }: { v: KidView; fname: Fname; cardName: (id: string) => string }): ReactNode {
  const region = (r: number): string => v.regions[r]?.name ?? String(r);
  const p = v.pending;
  return (
    <dl aria-label="Turn status" className="kid-status">
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
  onAct: (actionId: number) => void | Promise<unknown>;
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
  part = "all",
}: {
  /** "main": map and tables; "side": status, seats and results; "all": both (default). */
  part?: "all" | "main" | "side";
  click?: ClickToAct;
  v: KidView;
  /** Regions targeted by the legal actions available to the viewer. */
  legalRegions?: ReadonlySet<number>;
  hoverRegionFromAction?: number | null;
}) {
  const [cardHover, setCardHover] = useState<number | null>(null);
  const [choosing, setChoosing] = useState<number | null>(null);
  const [held, setHeld] = useState<number | null>(null);
  // Symmetric swap (Manoeuvre, Outmanoeuvre 1-for-1): either follower may be clicked first; the
  // pair is submitted in the engine's canonical order (lower region first).
  const pairs = v.swap_pairs ?? [];
  const swapping = !!click && pairs.length > 0;
  const heldId = swapping && held !== null && partnersOf(pairs, held).length > 0 ? held : null;
  const swapPicks = swapping ? (heldId === null ? firstPicks(pairs) : partnersOf(pairs, heldId)) : [];
  const clickable: LegalAction[] = swapping
    ? swapPicks.map((p) => ({
        id: p.id,
        kind: "follower",
        region: p.region,
        faction: p.faction,
        label: `Swap ${v.faction_names[p.faction] ?? p.faction} in ${v.regions[p.region]?.name ?? p.region}`,
      }))
    : (click?.actions ?? []);
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
    if (!swapping) {
      void click?.onAct(id);
      return;
    }
    if (heldId === null) {
      setHeld(id);
      return;
    }
    const seq = canonicalSequence(pairs, heldId, id);
    setHeld(null);
    if (!seq || !click) return;
    void (async () => {
      await click.onAct(seq[0]);
      await click.onAct(seq[1]);
    })();
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
  const main = (
    <>
      <p>
        Regions resolved: {v.struggles_resolved} of {v.track.length}
      </p>
      {swapping && (
        <p role="status" data-testid="swap-hint">
          {heldId === null
            ? "Swap: click the first follower (either one of the pair)."
            : "Swap: click the follower to swap it with."}{" "}
          {heldId !== null && (
            <button type="button" onClick={() => setHeld(null)}>
              Cancel selection
            </button>
          )}
        </p>
      )}
      <div style={{ position: "relative" }}>
        <MapBoard
          v={v}
          highlightRegions={swapping ? new Set(byRegion.keys()) : legalRegions}
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
      <details className="kid-tables">
      <summary>Track and region tables</summary>
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
      </details>
    </>
  );
  const side = (
    <>
      <Header v={v} fname={fname} cardName={cardName} />
      <Players
        v={v}
        playable={playable}
        playableSeat={v.current_player}
        onPlayCard={click ? submit : undefined}
      />
      {v.is_terminal && <ScoringPanel v={v} fname={fname} />}
    </>
  );
  return (
    <div aria-label={part === "side" ? "King is Dead status" : "King is Dead board"}>
      {part !== "side" && main}
      {part !== "main" && side}
    </div>
  );
}

export default function Board({
  game,
  part = "all",
  hoverAction = null,
  canAct = false,
  onAct,
  labelFor,
}: {
  game: GameView;
  part?: "all" | "main" | "side";
  hoverAction?: number | null;
  canAct?: boolean;
  onAct?: (actionId: number) => void | Promise<unknown>;
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
    <KidBoard part={part} v={v} legalRegions={legalRegions} hoverRegionFromAction={hovered} click={click} />
  );
}
