import type { components } from "../api/schema";

type HistoryEntry = components["schemas"]["HistoryEntry"];

interface Props {
  history: HistoryEntry[];
}

/** Past actions (labelled by the server), oldest first; kept scrolled to the newest. */
export default function ActionLog({ history }: Props) {
  return (
    <ol
      aria-label="Action log"
      ref={(el) => {
        if (el) el.scrollTop = el.scrollHeight;
      }}
      style={{ maxHeight: "10em", overflowY: "auto", paddingLeft: "2em" }}
    >
      {history.map((e) => (
        <li key={e.index}>
          {e.actor === null ? "" : `P${e.actor}: `}
          {e.label}
        </li>
      ))}
    </ol>
  );
}
