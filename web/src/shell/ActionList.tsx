import type { LegalAction } from "./useGame";

interface Props {
  actions: LegalAction[];
  disabled: boolean;
  onAct: (id: number) => void;
  /** Optional display label (e.g. adds a slot number); the action id is unchanged. */
  labelFor?: (a: LegalAction) => string;
  onHover?: (id: number | null) => void;
}

export default function ActionList({ actions, disabled, onAct, labelFor, onHover }: Props) {
  if (actions.length === 0) return <p>No actions available.</p>;
  return (
    <ul aria-label="Legal actions" style={{ listStyle: "none", padding: 0 }}>
      {actions.map((a) => (
        <li key={a.id}>
          <button
            type="button"
            disabled={disabled}
            onClick={() => onAct(a.id)}
            onMouseEnter={() => onHover?.(a.id)}
            onMouseLeave={() => onHover?.(null)}
            onFocus={() => onHover?.(a.id)}
            onBlur={() => onHover?.(null)}
          >
            {labelFor ? labelFor(a) : a.label}
          </button>
        </li>
      ))}
    </ul>
  );
}
