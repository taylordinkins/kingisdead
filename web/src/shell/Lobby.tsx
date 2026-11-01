import { useState, type FormEvent } from "react";
import { api } from "../api/client";
import { SEAT_PRESETS } from "./seatTypes";
import type { SeatType } from "./useGame";

interface Props {
  onCreated: (gameId: string) => void;
  onOpenEditor?: () => void;
}

export default function Lobby({ onCreated, onOpenEditor }: Props) {
  const [players, setPlayers] = useState(2);
  const [seats, setSeats] = useState<SeatType[]>(["human", "random", "random"]);
  const [seed, setSeed] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const trimmed = seed.trim();
      const { data, error: err } = await api.POST("/api/games", {
        body: {
          game: "king_is_dead",
          params: { num_players: players },
          seats: seats.slice(0, players),
          ...(trimmed !== "" ? { seed: Number(trimmed) } : {}),
        },
      });
      if (data) onCreated(data.id);
      else {
        const detail = (err as { detail?: unknown } | undefined)?.detail;
        setError(typeof detail === "string" ? detail : JSON.stringify(detail ?? err));
      }
    } catch (ex) {
      setError(ex instanceof Error ? ex.message : "Network error");
    } finally {
      setBusy(false);
    }
  }

  const seedBad = seed.trim() !== "" && !Number.isInteger(Number(seed.trim()));

  return (
    <form onSubmit={(e) => void submit(e)}>
      <h2>New game</h2>
      <label>
        Players{" "}
        <select value={players} onChange={(e) => setPlayers(Number(e.target.value))}>
          <option value={2}>2</option>
          <option value={3}>3</option>
        </select>
      </label>
      {seats.slice(0, players).map((s, i) => (
        <div key={i}>
          <label>
            Seat {i}{" "}
            <select
              value={s}
              onChange={(e) =>
                setSeats(seats.map((x, j) => (j === i ? (e.target.value as SeatType) : x)))
              }
            >
              {SEAT_PRESETS.map((p) => (
                <option key={p.value} value={p.value}>
                  {p.label}
                </option>
              ))}
            </select>
          </label>
        </div>
      ))}
      <label>
        Seed (optional){" "}
        <input value={seed} onChange={(e) => setSeed(e.target.value)} inputMode="numeric" />
      </label>
      <div>
        <button type="submit" disabled={busy || seedBad}>
          Create game
        </button>
      </div>
      {error && <p role="alert">Error: {error}</p>}
      {onOpenEditor && (
        <p>
          <button type="button" onClick={onOpenEditor}>
            Set up a table (setup editor)
          </button>
        </p>
      )}
    </form>
  );
}
