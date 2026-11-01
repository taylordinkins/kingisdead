import type { KeyboardEvent } from "react";
import { Token } from "../games/king-is-dead/board/factions";
import { MAP_HEIGHT, MAP_WIDTH, REGION_SHAPES } from "../games/king-is-dead/board/geometry";
import { FACTIONS, REGIONS, type Region, type ScenarioModel } from "./model";

interface Props {
  model: ScenarioModel;
  selected: Region;
  onSelect: (r: Region) => void;
  /** Regions to flag as offending (from validation issues). */
  bad: ReadonlySet<Region>;
}

/** Read-mostly SVG map for the editor: followers per faction, slot numbers, closed states. Click selects. */
export default function EditorMap({ model, selected, onSelect, bad }: Props) {
  return (
    <svg
      className="kid-map"
      viewBox={`0 0 ${MAP_WIDTH} ${MAP_HEIGHT}`}
      role="group"
      aria-label="Editor map"
      style={{ width: "100%", maxWidth: 720, background: "var(--sea)", borderRadius: 8 }}
    >
      {REGION_SHAPES.map((shape) => {
        const region = REGIONS[shape.index] as Region;
        const d = shape.points.map(([x, y], i) => `${i ? "L" : "M"}${x},${y}`).join(" ") + " Z";
        const [cx, cy] = shape.centre;
        const slot = model.slots.indexOf(region) + 1;
        const isSel = region === selected;
        const isBad = bad.has(region);
        const st = model.kind === "state" ? model.regionState[region] : undefined;
        const onKey = (e: KeyboardEvent) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onSelect(region);
          }
        };
        return (
          <g
            key={region}
            role="button"
            tabIndex={0}
            aria-pressed={isSel}
            aria-label={`Select ${region}${isBad ? " (has a problem)" : ""}`}
            data-testid={`map-${region}`}
            data-bad={isBad ? "true" : undefined}
            onClick={() => onSelect(region)}
            onKeyDown={onKey}
            style={{ cursor: "pointer" }}
          >
            <path d={d} fill={`var(--t-${shape.terrain})`} stroke="var(--paper)" strokeWidth={8} strokeLinejoin="round" />
            <path
              d={d}
              fill="none"
              strokeLinejoin="round"
              stroke={isBad ? "#c0392b" : isSel ? "var(--gold)" : "none"}
              strokeWidth={isBad ? 7 : 6}
              strokeDasharray={isBad ? "10 5" : undefined}
            />
            <text x={cx} y={cy - 14} textAnchor="middle" fontSize={24} fontWeight={700} fill="var(--ink)" stroke="var(--paper)" strokeWidth={4} paintOrder="stroke">
              {region}
            </text>
            <circle cx={shape.points[0]![0] + 30} cy={shape.points[0]![1] + 26} r={15} fill="var(--card)" stroke="var(--card-edge)" strokeWidth={2} />
            <text x={shape.points[0]![0] + 30} y={shape.points[0]![1] + 32} textAnchor="middle" fontSize={17} fontWeight={800} fill="var(--ink)">
              {slot}
            </text>
            {st && (
              <text x={cx} y={cy + 56} textAnchor="middle" fontSize={16} fontStyle="italic" fill="var(--ink)" stroke="var(--paper)" strokeWidth={3} paintOrder="stroke">
                {st === "unstable" ? "unstable" : `held by ${st}`}
              </text>
            )}
            {FACTIONS.map((f, i) => {
              const n = model.regions[region][f];
              const x = cx + (i - 1) * 50;
              return (
                <g key={f} opacity={n > 0 ? 1 : 0.28} data-testid={`count-${region}-${f}`}>
                  <Token faction={i} x={x} y={cy + 16} r={14} letter={false} />
                  <text x={x} y={cy + 22} textAnchor="middle" fontSize={17} fontWeight={800} fill="#fff">
                    {n}
                  </text>
                </g>
              );
            })}
          </g>
        );
      })}
    </svg>
  );
}
