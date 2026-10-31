import type { LegalAction } from "./useGame";

interface Props {
  actions: LegalAction[];
  disabled: boolean;
  onAct: (id: number) => void;
}

export default function ActionList({ actions, disabled, onAct }: Props) {
  if (actions.length === 0) return <p>No actions available.</p>;
  return (
    <ul aria-label="Legal actions" style={{ listStyle: "none", padding: 0 }}>
      {actions.map((a) => (
        <li key={a.id}>
          <button type="button" disabled={disabled} onClick={() => onAct(a.id)}>
            {a.label}
          </button>
        </li>
      ))}
    </ul>
  );
}
