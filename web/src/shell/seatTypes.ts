import type { SeatType } from "./useGame";

/** Seat-type choices offered in the lobby (values are validated server-side by pattern). */
export const SEAT_PRESETS: { value: SeatType; label: string }[] = [
  { value: "human", label: "Human" },
  { value: "random", label: "Random bot" },
  { value: "heuristic", label: "Heuristic bot" },
  { value: "mcts:20", label: "MCTS Easy (20 sims)" },
  { value: "mcts:100", label: "MCTS Medium (100 sims)" },
  { value: "mcts:400", label: "MCTS Hard (400 sims)" },
  { value: "trained:az-2p-v1", label: "Trained (AlphaZero)" },
];

/** Display name for a seat type, e.g. "Heuristic", "MCTS Medium", "MCTS (50 sims)". */
export function seatTypeName(t: string): string {
  const preset = SEAT_PRESETS.find((p) => p.value === t);
  if (preset) return preset.label.replace(/ bot$/, "").replace(/ \(\d+ sims\)$/, "");
  const m = /^mcts(?::(\d+))?$/.exec(t);
  if (m) return m[1] ? `MCTS (${m[1]} sims)` : "MCTS";
  if (t.startsWith("trained:")) return `Trained (${t.slice(8)})`;
  return t.charAt(0).toUpperCase() + t.slice(1);
}

export function thinkingText(seatType: string, seat: number): string {
  return `${seatTypeName(seatType)} (P${seat}) is thinking…`;
}
