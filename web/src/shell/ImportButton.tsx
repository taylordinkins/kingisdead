import { useState, type ChangeEvent } from "react";
import { api } from "../api/client";
import { errorText } from "./useGame";

interface Props {
  onImported: (gameId: string) => void;
}

/** File input that posts a replay export to /api/games/import. */
export default function ImportButton({ onImported }: Props) {
  const [error, setError] = useState<string | null>(null);

  async function pick(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setError(null);
    try {
      const body = JSON.parse(await file.text());
      const { data, error: err } = await api.POST("/api/games/import", { body });
      if (data) onImported(data.id);
      else setError(errorText(err));
    } catch (ex) {
      setError(ex instanceof Error ? ex.message : "Import failed");
    }
  }

  return (
    <span>
      <label>
        Import replay{" "}
        <input type="file" accept="application/json,.json" onChange={(e) => void pick(e)} />
      </label>
      {error && <p role="alert">Import error: {error}</p>}
    </span>
  );
}
