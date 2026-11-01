import { api } from "../api/client";
import { toScenarioJson } from "./json";
import type { ScenarioModel } from "./model";

export interface ServerValidation {
  ok: boolean;
  /** The server's rejection text (e.g. "V4: closed regions ..."), when not ok. */
  detail?: string;
  /** Id of the session the server created as a side effect when ok (there is no validate-only endpoint). */
  gameId?: string;
}

/**
 * Authoritative check via the existing API: POST /api/games with the scenario (422 + detail when
 * scenario.py rejects it). There is no validate-only endpoint, so a successful call creates a throwaway
 * session; call this on explicit "check with server" / "play", not on every keystroke.
 */
export async function serverValidate(model: ScenarioModel): Promise<ServerValidation> {
  const json = toScenarioJson(model);
  const { data, error, response } = await api.POST("/api/games", {
    body: {
      game: "king_is_dead",
      params: { num_players: model.players },
      seats: Array<"human">(model.players).fill("human"),
      scenario: json,
    },
  });
  if (data) return { ok: true, gameId: (data as { game_id?: string }).game_id };
  const detail = (error as { detail?: unknown } | undefined)?.detail;
  return { ok: false, detail: typeof detail === "string" ? detail : `HTTP ${response.status}` };
}
