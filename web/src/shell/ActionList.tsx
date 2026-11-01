import Tip from "./Tip";
import type { LegalAction } from "./useGame";

interface Props {
  actions: LegalAction[];
  disabled: boolean;
  onAct: (id: number) => void;
  /** Optional display label (e.g. adds a slot number); the action id is unchanged. */
  labelFor?: (a: LegalAction) => string;
  onHover?: (id: number | null) => void;
  /** Optional tooltip text for an action (e.g. what a card does). */
  describe?: (a: LegalAction) => string | undefined;
}

const isCard = (a: LegalAction): boolean => a.kind === "play";

/** Legal actions as buttons; card plays come first as prominent card-like buttons. */
export default function ActionList({ actions, disabled, onAct, labelFor, onHover, describe }: Props) {
  if (actions.length === 0) return <p>No actions available.</p>;
  const ordered = [...actions.filter(isCard), ...actions.filter((a) => !isCard(a))];
  const lastCard = ordered.filter(isCard).length - 1;
  return (
    <ul aria-label="Legal actions" className="kid-actions">
      {ordered.map((a, i) => (
        <li key={a.id} className={isCard(a) ? "kid-card" : undefined} style={i === lastCard && lastCard < ordered.length - 1 ? { marginRight: "100%" } : undefined}>
          <Tip text={describe?.(a)}>
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
          </Tip>
        </li>
      ))}
    </ul>
  );
}
