import type { CSSProperties } from "react";
import type { components } from "../api/schema";

type HistoryEntry = components["schemas"]["HistoryEntry"];

export interface ActorStyle {
  fill: string;
  ink: string;
}

interface Props {
  history: HistoryEntry[];
  /** Optional per-seat colours from the game plugin. */
  actorStyle?: (seat: number) => ActorStyle;
}

export type LogItem =
  | { kind: "action"; entry: HistoryEntry; n: number }
  | { kind: "chance"; entries: HistoryEntry[]; leading: boolean };

/**
 * Groups runs of consecutive chance entries (actor null). Player actions are numbered the same
 * way as dev-mode Rewind ("player action N" = N actions taken, chance excluded).
 */
export function groupHistory(history: HistoryEntry[]): LogItem[] {
  const items: LogItem[] = [];
  let n = 0;
  for (const e of history) {
    if (e.actor === null) {
      const last = items[items.length - 1];
      if (last && last.kind === "chance") last.entries.push(e);
      else items.push({ kind: "chance", entries: [e], leading: items.length === 0 });
    } else {
      n += 1;
      items.push({ kind: "action", entry: e, n });
    }
  }
  return items;
}

const badge = (s: ActorStyle): CSSProperties => ({
  background: s.fill,
  color: s.ink,
  borderRadius: 4,
  padding: "0 0.35em",
  fontWeight: "bold",
});

/** Past actions (labelled by the server), oldest first; kept scrolled to the newest. */
export default function ActionLog({ history, actorStyle }: Props) {
  const items = groupHistory(history);
  const lastIndex = history.length - 1;
  const current = (idx: number) => (idx === lastIndex ? ({ "aria-current": "step" } as const) : {});
  const latest = <strong> {"<"} latest</strong>;
  return (
    <ol
      aria-label="Action log"
      ref={(el) => {
        if (el) el.scrollTop = el.scrollHeight;
      }}
      style={{ maxHeight: "10em", overflowY: "auto", paddingLeft: "2em" }}
    >
      {items.map((it) => {
        if (it.kind === "action") {
          const e = it.entry;
          return (
            <li key={e.index} {...current(e.index)}>
              <span style={e.actor !== null && actorStyle ? badge(actorStyle(e.actor)) : undefined}>
                P{e.actor}:
              </span>{" "}
              {e.label} <small>(action {it.n})</small>
              {e.index === lastIndex && latest}
            </li>
          );
        }
        const first = it.entries[0]!;
        const lastEntry = it.entries[it.entries.length - 1]!;
        if (it.entries.length === 1) {
          return (
            <li key={first.index} {...current(first.index)}>
              {first.label}
              {first.index === lastIndex && latest}
            </li>
          );
        }
        const title = it.leading
          ? `Setup (${it.entries.length} random draws)`
          : `Random draws (${it.entries.length})`;
        return (
          <li key={first.index} {...current(lastEntry.index)}>
            <details>
              <summary>
                {title}
                {lastEntry.index === lastIndex && latest}
              </summary>
              <ol>
                {it.entries.map((e) => (
                  <li key={e.index}>{e.label}</li>
                ))}
              </ol>
            </details>
          </li>
        );
      })}
    </ol>
  );
}
