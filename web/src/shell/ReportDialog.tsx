import { useState, type FormEvent } from "react";
import { api } from "../api/client";
import { errorText } from "./useGame";

interface Props {
  gameId: string;
  onClose: () => void;
}

const CATEGORIES = ["engine", "ui", "other"] as const;

export default function ReportDialog({ gameId, onClose }: Props) {
  const [note, setNote] = useState("");
  const [category, setCategory] = useState<string>("other");
  const [error, setError] = useState<string | null>(null);
  const [reportId, setReportId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (note.trim() === "") {
      setError("Note is required");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const { data, error: err } = await api.POST("/api/games/{game_id}/report", {
        params: { path: { game_id: gameId } },
        body: { note, category },
      });
      if (data) setReportId(data.report_id);
      else setError(errorText(err));
    } catch (ex) {
      setError(ex instanceof Error ? ex.message : "Network error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div role="dialog" aria-modal="true" aria-label="Report a problem">
      <form onSubmit={(e) => void submit(e)}>
        <h2>Report a problem</h2>
        <label>
          Category{" "}
          <select value={category} onChange={(e) => setCategory(e.target.value)}>
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </label>
        <div>
          <label>
            Note <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={4} />
          </label>
        </div>
        {reportId && <p role="status">Report sent. Report id: {reportId}</p>}
        {error && <p role="alert">Error: {error}</p>}
        <button type="submit" disabled={busy || reportId !== null}>
          Submit report
        </button>{" "}
        <button type="button" onClick={onClose}>
          Close report
        </button>
      </form>
    </div>
  );
}
