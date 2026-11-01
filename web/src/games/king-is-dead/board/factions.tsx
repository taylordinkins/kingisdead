import type { ReactNode } from "react";

/** Faction look: colour-blind-safe (Okabe-Ito) colours plus a distinct shape and letter each. */
export interface FactionStyle {
  fill: string;
  stroke: string;
  letter: string;
  shape: "circle" | "square" | "triangle";
  /** Text colour on top of fill. */
  ink: string;
}

export const FACTION_STYLES: FactionStyle[] = [
  { fill: "#0072B2", stroke: "#003e63", letter: "S", shape: "circle", ink: "#ffffff" },
  { fill: "#009E73", stroke: "#005a41", letter: "W", shape: "square", ink: "#ffffff" },
  { fill: "#D55E00", stroke: "#7a3500", letter: "E", shape: "triangle", ink: "#ffffff" },
];

export const factionStyle = (f: number): FactionStyle =>
  FACTION_STYLES[f] ?? { fill: "#888", stroke: "#444", letter: "?", shape: "circle", ink: "#fff" };

/** Player disc colours: distinct from the faction colours; each also carries its number. */
export const PLAYER_STYLES = [
  { fill: "#CC79A7", ink: "#2a0f1e" },
  { fill: "#F0E442", ink: "#3a3500" },
  { fill: "#d8dde3", ink: "#1f2933" },
  { fill: "#56B4E9", ink: "#06202f" },
];
export const playerStyle = (p: number) => PLAYER_STYLES[p % PLAYER_STYLES.length]!;

/** A follower token centred on (x, y). */
export function Token({
  faction,
  x,
  y,
  r = 11,
  letter = true,
}: {
  faction: number;
  x: number;
  y: number;
  r?: number;
  letter?: boolean;
}): ReactNode {
  const s = factionStyle(faction);
  const common = { fill: s.fill, stroke: s.stroke, strokeWidth: 1.6 };
  let body: ReactNode;
  if (s.shape === "circle") body = <circle cx={x} cy={y} r={r} {...common} />;
  else if (s.shape === "square")
    body = <rect x={x - r * 0.9} y={y - r * 0.9} width={r * 1.8} height={r * 1.8} rx={r * 0.25} {...common} />;
  else
    body = (
      <polygon
        points={`${x},${y - r * 1.1} ${x + r * 1.1},${y + r * 0.85} ${x - r * 1.1},${y + r * 0.85}`}
        strokeLinejoin="round"
        {...common}
      />
    );
  return (
    <g>
      {body}
      {letter && (
        <text
          x={x}
          y={y + (s.shape === "triangle" ? r * 0.55 : r * 0.38)}
          textAnchor="middle"
          fontSize={r * 1.0}
          fontWeight={700}
          fill={s.ink}
          fontFamily="Georgia, 'Times New Roman', serif"
        >
          {s.letter}
        </text>
      )}
    </g>
  );
}

/** Heraldic shield with an initial, centred on (x, y). */
export function Crest({
  x,
  y,
  scale = 1,
  initial,
  muted = false,
}: {
  x: number;
  y: number;
  scale?: number;
  initial: string;
  muted?: boolean;
}): ReactNode {
  return (
    <g transform={`translate(${x} ${y}) scale(${scale})`} opacity={muted ? 0.55 : 1}>
      <path
        d="M-14,-16 H14 V4 C14,13 5,19 0,22 C-5,19 -14,13 -14,4 Z"
        className="kid-crest"
        strokeWidth={2}
        strokeLinejoin="round"
      />
      <path d="M-14,-5 H14" className="kid-crest-band" strokeWidth={2} />
      <text
        x={0}
        y={11}
        textAnchor="middle"
        fontSize={16}
        fontWeight={700}
        className="kid-crest-text"
        fontFamily="Georgia, 'Times New Roman', serif"
      >
        {initial}
      </text>
    </g>
  );
}
