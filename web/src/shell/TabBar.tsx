export type ScreenTab = "play" | "board" | "log";

const TABS: { id: ScreenTab; label: string }[] = [
  { id: "play", label: "Play" },
  { id: "board", label: "Board" },
  { id: "log", label: "Log" },
];

/** Narrow-screen pane switcher; hidden by CSS on wide screens. */
export default function TabBar({
  value,
  onChange,
}: {
  value: ScreenTab;
  onChange: (t: ScreenTab) => void;
}) {
  return (
    <div className="kid-tabs" role="tablist" aria-label="Game sections">
      {TABS.map((t) => (
        <button
          key={t.id}
          type="button"
          role="tab"
          aria-selected={value === t.id}
          onClick={() => onChange(t.id)}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}
