import type { ReactNode } from "react";
import type { KidView } from "../types";
import { Token, playerStyle } from "./factions";

const STYLE = `
.kid-panels{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,240px),1fr));gap:8px;margin:8px 0}
.kid-panel{border:2px solid #9b7f4b;border-radius:10px;padding:6px 8px;min-width:0;overflow-wrap:anywhere}
.kid-panel[data-current=true]{box-shadow:0 0 0 3px #d99a00}
.kid-panel h4{margin:0 0 4px;display:flex;align-items:center;gap:6px;flex-wrap:wrap}
.kid-row{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin:3px 0}
.kid-lbl{font-size:.8em;opacity:.8;min-width:3.5em}
.kid-chip{display:inline-flex;align-items:center;gap:3px;border:1px solid #9b7f4b;border-radius:12px;padding:0 6px;font-size:.85em}
button.kid-chip{background:inherit;color:inherit;font:inherit;font-size:.85em;cursor:pointer;border-color:#d99a00;border-width:2px}
button.kid-chip:hover{background:rgba(217,154,0,.25)}
button.kid-chip:focus-visible{outline:3px solid #d99a00;outline-offset:2px}
`;

function Count({ faction, n, name }: { faction: number; n: number; name: string }): ReactNode {
  return (
    <span
      className="kid-chip"
      data-testid={`count-${faction}`}
      aria-label={`${n} ${name}`}
      style={{ opacity: n === 0 ? 0.45 : 1 }}
    >
      <svg width={22} height={22} viewBox="-12 -12 24 24" aria-hidden="true">
        <Token faction={faction} x={0} y={0} r={9} />
      </svg>
      ×{n}
    </span>
  );
}

export function Disc({ player, size = 24 }: { player: number; size?: number }): ReactNode {
  const ps = playerStyle(player);
  return (
    <svg width={size} height={size} viewBox="-12 -12 24 24" aria-hidden="true">
      <circle r={10.5} fill={ps.fill} stroke="#222" strokeWidth={2} />
      <text y={4} textAnchor="middle" fontSize={11} fontWeight={800} fill={ps.ink}>{`P${player}`}</text>
    </svg>
  );
}

/** Per-seat court, hand and negotiation disc, plus the shared supply. */
export function Players({
  v,
  playable,
  playableSeat,
  onPlayCard,
}: {
  v: KidView;
  /** Card id (as in the hand map) -> legal play action; only for the seat `playableSeat`. */
  playable?: ReadonlyMap<string, { id: number; label: string }>;
  playableSeat?: number | null;
  onPlayCard?: (actionId: number) => void;
}): ReactNode {
  const fnames = v.faction_names;
  const seats = Array.from({ length: v.num_players }, (_, p) => p);
  const cardName = (id: string): string => v.card_names[id] ?? `Card ${id}`;
  const regionName = (r: number): string => v.regions[r]?.name ?? `Region ${r}`;
  const slotOf = (r: number): number | undefined => v.track.find((t) => t.region === r)?.slot;
  return (
    <section aria-label="Players" className="kid-panels">
      <style>{STYLE}</style>
      {seats.map((p) => {
        const court = v.courts[p] ?? [];
        const hand = Object.entries(v.hands[p] ?? {}).filter(([, n]) => n > 0);
        const disc = v.negotiation_discs[p];
        const slot = disc == null ? undefined : slotOf(disc);
        const ps = playerStyle(p);
        return (
          <div
            key={p}
            className="kid-panel"
            role="group"
            aria-label={`Player ${p}`}
            data-testid={`player-${p}`}
            data-current={v.current_player === p ? "true" : undefined}
            style={{ borderColor: ps.fill }}
          >
            <h4>
              <Disc player={p} />
              {`P${p}`}
              {v.seat === p ? " (you)" : ""}
              {v.current_player === p ? " - to act" : ""}
            </h4>
            <div className="kid-row" role="group" aria-label={`P${p} court`}>
              <span className="kid-lbl">Court</span>
              {fnames.map((n, f) => (
                <Count key={f} faction={f} n={court[f] ?? 0} name={n} />
              ))}
            </div>
            <div className="kid-row" role="group" aria-label={`P${p} hand`}>
              <span className="kid-lbl">Hand</span>
              {hand.length === 0 && <span>empty</span>}
              {hand.map(([c, n]) => {
                const text = `${cardName(c)}${n > 1 ? ` ×${n}` : ""}`;
                const act = p === playableSeat && onPlayCard ? playable?.get(c) : undefined;
                return act ? (
                  <button
                    type="button"
                    className="kid-chip"
                    key={c}
                    aria-label={act.label}
                    onClick={() => onPlayCard?.(act.id)}
                  >
                    {text}
                  </button>
                ) : (
                  <span className="kid-chip" key={c}>
                    {text}
                  </span>
                );
              })}
            </div>
            <div className="kid-row" role="group" aria-label={`P${p} negotiation disc`}>
              <span className="kid-lbl">Disc</span>
              {disc == null ? (
                <span>in hand</span>
              ) : (
                <span data-testid={`disc-on-${p}`}>
                  on {regionName(disc)}
                  {slot === undefined ? "" : ` (slot ${slot + 1})`}
                </span>
              )}
            </div>
          </div>
        );
      })}
      <div className="kid-panel" role="group" aria-label="Supply" data-testid="supply">
        <h4>Supply</h4>
        <div className="kid-row">
          {fnames.map((n, f) => (
            <Count key={f} faction={f} n={v.supply[f] ?? 0} name={n} />
          ))}
        </div>
      </div>
    </section>
  );
}
