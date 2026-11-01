import type { KeyboardEvent, ReactNode } from "react";
import type { KidView, Region, TrackSlot } from "../types";
import { Crest, Token, factionStyle, playerStyle } from "./factions";
import { DRAWN_BORDERS, MAP_HEIGHT, MAP_WIDTH, REGION_SHAPES, type RegionShape } from "./geometry";

export interface MapBoardProps {
  v: KidView;
  /** Hook for click-to-act (unit 4); defaults to no-op and regions stay non-interactive. */
  onRegionClick?: (region: number) => void;
  /** Regions that accept a click; when omitted every region does (if onRegionClick is set). */
  clickableRegions?: ReadonlySet<number>;
  /** Accessible name of the click action for a region (the action label). */
  regionActionLabel?: (region: number) => string | undefined;
  /** Regions to draw with a highlight ring (e.g. legal targets). */
  highlightRegions?: ReadonlySet<number>;
  /** Region cross-highlighted (hovered action or card); drawn with a gold ring on map and track. */
  hoverRegion?: number | null;
  onHoverRegion?: (region: number | null) => void;
}

const TRACK_Y = 652;
const CARD_W = 114;
const CARD_H = 116;
const CARD_PITCH = 122;
export const VIEW_H = TRACK_Y + CARD_H + 16;

const SERIF = "Georgia, 'Palatino Linotype', 'Book Antiqua', 'Times New Roman', serif";

const STYLE = `
.kid-map{--paper:#efe3c8;--paper2:#e3d2ab;--ink:#3b2d1a;--ink-soft:#6d5a3d;--sea:#a9c4cf;--sea2:#8fb0be;
--road:#7a5a30;--card:#f7efdc;--card-edge:#9b7f4b;--back:#5b3a29;--back2:#7a4f37;--gold:#d99a00;
--crest:#f7efdc;--crest-edge:#5b3a29;--crest-band:#c9a24a;--crest-ink:#5b3a29;--shadow:rgba(60,40,10,.35);
--t-highland:#b9c38d;--t-highland2:#8fa072;--t-moor:#cfc08e;--t-moor2:#b0a074;--t-hill:#c3c999;--t-hill2:#9eaa7a;
--t-plain:#dbd49a;--t-plain2:#c3bd7e;--t-marsh:#b8c9a0;--t-marsh2:#92ab86;--t-coast:#d9cfa0;--t-coast2:#bfb88a;}
@media (prefers-color-scheme: dark){.kid-map{--paper:#2b2a24;--paper2:#201f1a;--ink:#f0e6cc;--ink-soft:#c9b98f;
--sea:#1f3440;--sea2:#17272f;--road:#d9b46a;--card:#3a3629;--card-edge:#b99a5a;--back:#4a2f22;--back2:#6a4331;
--gold:#ffc83d;--crest:#3a3629;--crest-edge:#e3c98a;--crest-band:#b8903a;--crest-ink:#f0e6cc;--shadow:rgba(0,0,0,.55);
--t-highland:#4b5a3a;--t-highland2:#38442c;--t-moor:#5b5334;--t-moor2:#463f27;--t-hill:#4f5a3a;--t-hill2:#3c452c;
--t-plain:#645f35;--t-plain2:#4e4a29;--t-marsh:#3f5a46;--t-marsh2:#2f463a;--t-coast:#5e5638;--t-coast2:#4a442b;}}
.kid-map text{font-family:${SERIF}}
.kid-crest{fill:var(--crest);stroke:var(--crest-edge)}
.kid-crest-band{stroke:var(--crest-band)}
.kid-crest-text{fill:var(--crest-ink)}
.kid-region path.kid-fill{stroke:var(--paper);stroke-width:10;stroke-linejoin:round;paint-order:stroke}
.kid-region[role=button]{cursor:pointer}
.kid-region[role=button]:hover path.kid-fill{filter:brightness(1.07)}
.kid-region:focus-visible path.kid-outline{stroke:var(--gold);stroke-width:4}
.kid-region:focus,.kid-click:focus{outline:none}
.kid-click{cursor:pointer}
.kid-click:focus-visible rect{stroke:var(--gold);stroke-width:7}
`;

const TERRAINS = ["highland", "moor", "hill", "plain", "marsh", "coast"] as const;

function Defs(): ReactNode {
  return (
    <defs>
      {TERRAINS.map((t) => (
        <linearGradient key={t} id={`kid-g-${t}`} x1="0" y1="0" x2="0.4" y2="1">
          <stop offset="0" style={{ stopColor: `var(--t-${t})` }} />
          <stop offset="1" style={{ stopColor: `var(--t-${t}2)` }} />
        </linearGradient>
      ))}
      <linearGradient id="kid-sea" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" style={{ stopColor: "var(--sea)" }} />
        <stop offset="1" style={{ stopColor: "var(--sea2)" }} />
      </linearGradient>
      <radialGradient id="kid-vignette" cx="0.5" cy="0.45" r="0.75">
        <stop offset="0.65" stopColor="#000" stopOpacity="0" />
        <stop offset="1" stopColor="#000" stopOpacity="0.22" />
      </radialGradient>
      <pattern id="kid-dots" width="14" height="14" patternUnits="userSpaceOnUse">
        <circle cx="3" cy="4" r="1.3" fill="#000" opacity="0.13" />
        <circle cx="10" cy="11" r="1" fill="#000" opacity="0.10" />
      </pattern>
      <pattern id="kid-peaks" width="24" height="18" patternUnits="userSpaceOnUse">
        <path d="M2,14 L8,5 L14,14 M12,14 L17,8 L22,14" fill="none" stroke="#000" strokeOpacity="0.14" strokeWidth="1.4" strokeLinejoin="round" />
      </pattern>
      <pattern id="kid-waves" width="26" height="12" patternUnits="userSpaceOnUse">
        <path d="M0,6 Q6.5,0 13,6 T26,6" fill="none" stroke="#000" strokeOpacity="0.12" strokeWidth="1.3" />
      </pattern>
      <pattern id="kid-fields" width="18" height="18" patternUnits="userSpaceOnUse" patternTransform="rotate(28)">
        <path d="M0,9 H18" stroke="#000" strokeOpacity="0.09" strokeWidth="1.2" />
      </pattern>
      <pattern id="kid-unstable" width="12" height="12" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
        <rect width="12" height="12" fill="#8c1d18" opacity="0.28" />
        <rect width="5" height="12" fill="#3b0b09" opacity="0.38" />
      </pattern>
      <pattern id="kid-back" width="16" height="16" patternUnits="userSpaceOnUse">
        <path d="M8,1 L15,8 L8,15 L1,8 Z" fill="none" stroke="var(--crest-band)" strokeOpacity="0.45" strokeWidth="1.2" />
      </pattern>
      <filter id="kid-shadow" x="-10%" y="-10%" width="125%" height="130%">
        <feDropShadow dx="0" dy="4" stdDeviation="4" floodColor="#3c2808" floodOpacity="0.4" />
      </filter>
    </defs>
  );
}

const TEXTURE: Record<RegionShape["terrain"], string> = {
  highland: "kid-peaks",
  hill: "kid-peaks",
  moor: "kid-dots",
  plain: "kid-fields",
  marsh: "kid-waves",
  coast: "kid-waves",
};

const pathOf = (pts: [number, number][]): string =>
  `M${pts.map((p) => p.join(",")).join(" L")} Z`;

function bounds(pts: [number, number][]) {
  const xs = pts.map((p) => p[0]);
  const ys = pts.map((p) => p[1]);
  return { minX: Math.min(...xs), maxX: Math.max(...xs), minY: Math.min(...ys), maxY: Math.max(...ys) };
}

function Roads(): ReactNode {
  const centre = (i: number) => REGION_SHAPES[i]!.centre;
  return (
    <g aria-hidden="true" data-testid="roads">
      {DRAWN_BORDERS.map(([a, b]) => {
        const [ax, ay] = centre(a);
        const [bx, by] = centre(b);
        const at = (t: number) => [ax + (bx - ax) * t, ay + (by - ay) * t] as const;
        const [x1, y1] = at(0.36);
        const [x2, y2] = at(0.64);
        const [mx, my] = at(0.5);
        return (
          <g key={`${a}-${b}`} data-border={`${a}-${b}`}>
            <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="var(--paper)" strokeWidth={9} strokeLinecap="round" />
            <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="var(--road)" strokeWidth={3} strokeDasharray="1 7" strokeLinecap="round" />
            <circle cx={mx} cy={my} r={5.5} fill="var(--paper)" stroke="var(--road)" strokeWidth={2} />
          </g>
        );
      })}
    </g>
  );
}

function FollowerChip({ faction, n, x, y }: { faction: number; n: number; x: number; y: number }): ReactNode {
  const layers = Math.min(n, 4);
  return (
    <g data-testid={`followers-${faction}`}>
      {Array.from({ length: layers }, (_, i) => (
        <Token
          key={i}
          faction={faction}
          x={x - 10 + (layers - 1 - i) * 0 + i * 3.5}
          y={y - i * 3.5}
          r={11}
          letter={i === layers - 1}
        />
      ))}
      <text x={x + 12} y={y + 7} fontSize={20} fontWeight={700} fill="var(--ink)">
        {`×${n}`}
      </text>
    </g>
  );
}

function stateText(r: Region, fname: (f: number) => string): string {
  if (r.state === "controlled") return `Controlled by ${r.controller === null ? "?" : fname(r.controller)}`;
  if (r.state === "unstable") return "Unstable";
  return "Open";
}

function describe(r: Region, v: KidView): string {
  const fname = (f: number) => v.faction_names[f] ?? `Faction ${f}`;
  const counts = v.faction_names.map((n, f) => `${r.followers[f] ?? 0} ${n}`).join(", ");
  return `${r.name}: ${counts}; ${stateText(r, fname).toLowerCase()}`;
}

function RegionView({
  shape,
  v,
  current,
  highlighted,
  hovered,
  slot,
  onClick,
  onHover,
  actionLabel,
}: {
  shape: RegionShape;
  v: KidView;
  current: boolean;
  highlighted: boolean;
  hovered: boolean;
  slot: number | undefined;
  onClick?: (region: number) => void;
  onHover?: (region: number | null) => void;
  actionLabel?: string;
}): ReactNode {
  const r = v.regions[shape.index];
  if (!r) return null;
  const fname = (f: number) => v.faction_names[f] ?? `Faction ${f}`;
  const [cx, cy] = shape.centre;
  const b = bounds(shape.points);
  const closed = r.state !== "open";
  const present = v.faction_names.map((_, f) => f).filter((f) => (r.followers[f] ?? 0) > 0);
  const chipY = cy + (closed ? 30 : 22);
  const pitch = 66;
  const label = describe(r, v);
  const d = pathOf(shape.points);
  const ctl = r.state === "controlled" && r.controller !== null ? factionStyle(r.controller) : null;
  const interactive = onClick !== undefined;
  const key = (e: KeyboardEvent) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onClick?.(shape.index);
    }
  };
  return (
    <g
      className="kid-region"
      data-testid={`region-${shape.index}`}
      data-state={r.state}
      data-current={current ? "true" : undefined}
      data-highlighted={highlighted ? "true" : undefined}
      data-hover={hovered ? "true" : undefined}
      onMouseEnter={onHover ? () => onHover(shape.index) : undefined}
      onMouseLeave={onHover ? () => onHover(null) : undefined}
      role={interactive ? "button" : "group"}
      aria-label={interactive && actionLabel ? `${actionLabel}. ${label}` : label}
      tabIndex={interactive ? 0 : undefined}
      onClick={interactive ? () => onClick(shape.index) : undefined}
      onKeyDown={interactive ? key : undefined}
    >
      <title>{label}</title>
      <path d={d} className="kid-fill" fill={`url(#kid-g-${shape.terrain})`} filter="url(#kid-shadow)" />
      <path d={d} fill={`url(#${TEXTURE[shape.terrain]})`} pointerEvents="none" />
      {r.state === "unstable" && <path d={d} fill="url(#kid-unstable)" pointerEvents="none" />}
      <path
        d={d}
        className="kid-outline"
        fill="none"
        stroke={ctl ? ctl.fill : r.state === "unstable" ? "#8c1d18" : "var(--ink-soft)"}
        strokeWidth={ctl || r.state === "unstable" ? 4 : 1.5}
        strokeOpacity={closed ? 0.95 : 0.55}
        strokeLinejoin="round"
        pointerEvents="none"
      />
      {current && (
        <path d={d} fill="none" stroke="var(--gold)" strokeWidth={5} strokeLinejoin="round" strokeDasharray="14 7" pointerEvents="none" />
      )}
      {highlighted && (
        <path d={d} fill="none" stroke="#ffffff" strokeOpacity={0.9} strokeWidth={6} strokeLinejoin="round" pointerEvents="none" data-testid={`highlight-${shape.index}`} />
      )}
      {hovered && (
        <path d={d} fill="none" stroke="var(--gold)" strokeWidth={8} strokeLinejoin="round" pointerEvents="none" data-testid={`hover-${shape.index}`} />
      )}
      {slot !== undefined && (
        <g data-testid={`slot-badge-${shape.index}`} transform={`translate(${b.minX + 26} ${b.minY + 26})`} pointerEvents="none">
          <circle r={15} fill={highlighted ? "var(--gold)" : "var(--card)"} stroke="var(--card-edge)" strokeWidth={2} />
          <text y={6} textAnchor="middle" fontSize={17} fontWeight={800} fill={highlighted ? "#2b1d00" : "var(--ink)"}>{slot + 1}</text>
        </g>
      )}
      <text x={cx} y={cy - 12} textAnchor="middle" fontSize={25} fontWeight={700} fill="var(--ink)" stroke="var(--paper)" strokeWidth={4} paintOrder="stroke" pointerEvents="none">
        {shape.name}
      </text>
      {closed && (
        <text x={cx} y={cy + 8} textAnchor="middle" fontSize={15} fontStyle="italic" fill="var(--ink)" stroke="var(--paper)" strokeWidth={3} paintOrder="stroke" pointerEvents="none" data-testid={`state-${shape.index}`}>
          {stateText(r, fname)}
        </text>
      )}
      {ctl && r.controller !== null && (
        <g data-testid={`control-${shape.index}`} transform={`translate(${b.maxX - 30} ${b.minY + 26})`}>
          <circle r={19} fill="var(--paper)" opacity={0.9} />
          <Token faction={r.controller} x={0} y={0} r={14} />
        </g>
      )}
      {r.state === "unstable" && (
        <g data-testid={`unstable-${shape.index}`} transform={`translate(${b.maxX - 30} ${b.minY + 28})`}>
          <polygon points="0,-20 19,14 -19,14" fill="#c0392b" stroke="#fff" strokeWidth={2.5} strokeLinejoin="round" />
          <text y={9} textAnchor="middle" fontSize={20} fontWeight={800} fill="#fff">!</text>
        </g>
      )}
      <g pointerEvents="none">
        {present.map((f, i) => (
          <FollowerChip
            key={f}
            faction={f}
            n={r.followers[f] ?? 0}
            x={cx + (i - (present.length - 1) / 2) * pitch - 6}
            y={chipY}
          />
        ))}
      </g>
    </g>
  );
}

function TrackCard({
  t,
  v,
  current,
  highlighted,
  hovered,
  onHover,
  onClick,
  actionLabel,
}: {
  t: TrackSlot;
  v: KidView;
  current: boolean;
  highlighted: boolean;
  hovered: boolean;
  onHover?: (region: number | null) => void;
  onClick?: (region: number) => void;
  actionLabel?: string;
}): ReactNode {
  const x = 12 + t.slot * CARD_PITCH;
  const name = t.region === null ? "?" : (v.regions[t.region]?.name ?? `Region ${t.region}`);
  const state = t.region === null ? "not placed" : t.face_down ? "resolved" : "pending";
  const discs = t.discs.map((p) => `P${p}`).join(", ");
  const label = `Slot ${t.slot + 1}: ${name}, ${state}${discs ? `, negotiation discs: ${discs}` : ""}`;
  const cx = x + CARD_W / 2;
  const clickable = onClick !== undefined && highlighted && t.region !== null;
  const region = t.region;
  return (
    <g className={clickable ? "kid-click" : undefined} data-testid={`track-slot-${t.slot}`} data-face-down={t.face_down ? "true" : "false"} data-current={current ? "true" : undefined} role={clickable ? "button" : "group"} aria-label={clickable && actionLabel ? `${actionLabel}. ${label}` : label}
      tabIndex={clickable ? 0 : undefined}
      onKeyDown={clickable ? (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onClick(region as number); } } : undefined} data-highlighted={highlighted ? "true" : undefined} data-hover={hovered ? "true" : undefined}
      onMouseEnter={onHover && t.region !== null ? () => onHover(t.region) : undefined}
      onMouseLeave={onHover ? () => onHover(null) : undefined}
      onClick={onClick && highlighted && t.region !== null ? () => onClick(t.region as number) : undefined}
    >
      <title>{label}</title>
      <rect x={x} y={TRACK_Y} width={CARD_W} height={CARD_H} rx={10} fill={t.face_down ? "var(--back)" : "var(--card)"} stroke={current || highlighted || hovered ? "var(--gold)" : "var(--card-edge)"} strokeWidth={current || highlighted || hovered ? 5 : 2} strokeDasharray={highlighted && !hovered ? "9 5" : undefined} filter="url(#kid-shadow)" />
      {(highlighted || hovered) && <rect x={x - 4} y={TRACK_Y - 4} width={CARD_W + 8} height={CARD_H + 8} rx={13} fill="none" stroke="#ffffff" strokeWidth={2} pointerEvents="none" data-testid={`slot-highlight-${t.slot}`} />}
      {t.face_down && <rect x={x + 4} y={TRACK_Y + 4} width={CARD_W - 8} height={CARD_H - 8} rx={7} fill="url(#kid-back)" stroke="var(--crest-band)" strokeOpacity={0.6} strokeWidth={1.5} />}
      <circle cx={x + 18} cy={TRACK_Y + 18} r={12} fill={t.face_down ? "var(--back2)" : "var(--paper2)"} stroke="var(--card-edge)" strokeWidth={1.5} />
      <text x={x + 18} y={TRACK_Y + 24} textAnchor="middle" fontSize={16} data-testid={`slot-number-${t.slot}`} fontWeight={700} fill={t.face_down ? "#f0e6cc" : "var(--ink)"}>
        {t.slot + 1}
      </text>
      {t.region !== null && !t.face_down && <Crest x={cx} y={TRACK_Y + 52} scale={1.25} initial={name.charAt(0)} />}
      {t.face_down && <Crest x={cx} y={TRACK_Y + 52} scale={1.25} initial={name.charAt(0)} muted />}
      <text x={cx} y={TRACK_Y + 92} textAnchor="middle" fontSize={15} fontWeight={700} fill={t.face_down ? "#f0e6cc" : "var(--ink)"} stroke={t.face_down ? "var(--back)" : "none"} strokeWidth={3} paintOrder="stroke">
        {name}
      </text>
      {t.face_down && (
        <text x={cx} y={TRACK_Y + 108} textAnchor="middle" fontSize={12} fontStyle="italic" fill="#f0e6cc">
          resolved
        </text>
      )}
      {current && (
        <g>
          <rect x={x + CARD_W - 50} y={TRACK_Y - 11} width={44} height={20} rx={10} fill="var(--gold)" />
          <text x={x + CARD_W - 28} y={TRACK_Y + 4} textAnchor="middle" fontSize={12} fontWeight={800} fill="#2b1d00">NEXT</text>
        </g>
      )}
      {t.discs.map((p, i) => {
        const ps = playerStyle(p);
        const dx = x + CARD_W - 20 - i * 27;
        return (
          <g key={i} data-testid={`disc-${t.slot}-${p}`}>
            <circle cx={dx} cy={TRACK_Y + 26} r={11} fill={ps.fill} stroke="#222" strokeWidth={2} />
            <text x={dx} y={TRACK_Y + 31} textAnchor="middle" fontSize={13} fontWeight={800} fill={ps.ink}>{`P${p}`}</text>
          </g>
        );
      })}
    </g>
  );
}

function AssembleBanner({ v }: { v: KidView }): ReactNode {
  const f = v.pending.assemble_faction;
  if (f === null || f === undefined) return null;
  const name = v.faction_names[f] ?? `Faction ${f}`;
  const s = factionStyle(f);
  const text = `Placing ${name} followers`;
  return (
    <g role="status" aria-label={`Assemble: ${text}`} data-testid="assemble-banner" transform="translate(18 18)">
      <rect width={300} height={84} rx={14} fill="var(--card)" stroke={s.fill} strokeWidth={4} filter="url(#kid-shadow)" />
      <text x={20} y={27} fontSize={13} fontWeight={800} letterSpacing={2} fill="var(--ink-soft)">ASSEMBLE</text>
      <Token faction={f} x={46} y={56} r={19} />
      <text x={78} y={64} fontSize={20} fontWeight={700} fill="var(--ink)">{text}</text>
    </g>
  );
}

export function MapBoard({ v, onRegionClick, clickableRegions, regionActionLabel, highlightRegions, hoverRegion = null, onHoverRegion }: MapBoardProps) {
  const next = v.track.find((t) => !t.face_down);
  const currentSlot = next ? next.slot : -1;
  const currentRegion = next?.region ?? -1;
  const slotOf = new Map<number, number>();
  for (const t of v.track) if (t.region !== null) slotOf.set(t.region, t.slot);
  const legend = v.faction_names.map((n, f) => ({ n, f }));
  return (
    <svg
      className="kid-map"
      viewBox={`0 0 ${MAP_WIDTH} ${VIEW_H}`}
      width="100%"
      style={{ maxWidth: 1000, height: "auto", display: "block" }}
      role="group"
      aria-label="King is Dead map"
    >
      <style>{STYLE}</style>
      <Defs />
      <rect width={MAP_WIDTH} height={VIEW_H} rx={18} fill="url(#kid-sea)" />
      <rect y={0} width={MAP_WIDTH} height={MAP_HEIGHT} rx={18} fill="var(--paper)" opacity={0.22} />
      <rect width={MAP_WIDTH} height={VIEW_H} rx={18} fill="url(#kid-vignette)" pointerEvents="none" />
      <rect x={3} y={3} width={MAP_WIDTH - 6} height={VIEW_H - 6} rx={16} fill="none" stroke="var(--card-edge)" strokeWidth={3} />

      {REGION_SHAPES.map((s) => (
        <RegionView
          key={s.index}
          shape={s}
          v={v}
          current={s.index === currentRegion}
          highlighted={highlightRegions?.has(s.index) ?? false}
          hovered={hoverRegion === s.index}
          slot={slotOf.get(s.index)}
          onClick={onRegionClick && (clickableRegions?.has(s.index) ?? true) ? onRegionClick : undefined}
          onHover={onHoverRegion}
          actionLabel={regionActionLabel?.(s.index)}
        />
      ))}
      <Roads />

      <g aria-label="Legend" role="group" transform="translate(722 18)">
        <rect width={262} height={46} rx={12} fill="var(--card)" opacity={0.92} stroke="var(--card-edge)" strokeWidth={1.5} />
        {legend.map(({ n, f }, i) => (
          <g key={f} transform={`translate(${16 + i * 84} 23)`}>
            <Token faction={f} x={0} y={0} r={10} />
            <text x={16} y={5} fontSize={13} fill="var(--ink)">{n}</text>
          </g>
        ))}
      </g>
      <text x={982} y={90} textAnchor="end" fontSize={15} fontStyle="italic" fill="var(--ink)" stroke="var(--paper)" strokeWidth={3} paintOrder="stroke">
        {v.struggles_resolved >= v.track.length ? "All struggles resolved" : `Struggle ${v.struggles_resolved + 1} of ${v.track.length}`}
      </text>
      <AssembleBanner v={v} />

      <text x={14} y={TRACK_Y - 14} fontSize={15} fontStyle="italic" fill="var(--ink)">Region cards, in order of power struggle</text>
      {v.track.map((t) => (
        <TrackCard
          key={t.slot}
          t={t}
          v={v}
          current={t.slot === currentSlot}
          highlighted={t.region !== null && (highlightRegions?.has(t.region) ?? false)}
          hovered={t.region !== null && hoverRegion === t.region}
          onHover={onHoverRegion}
          onClick={onRegionClick}
          actionLabel={t.region === null ? undefined : regionActionLabel?.(t.region)}
        />
      ))}
    </svg>
  );
}
