import { rankingText } from "./ranking";
import type { KidView, ScoringStep } from "./types";

const player = (p: number): string => `P${p}`;
const list = (xs: readonly number[]): string => (xs.length ? xs.map(player).join(", ") : "none");

type Fname = (f: number | null) => string;

/** What each step measures, in rulebook terms (R-402..R-404). */
function stepTitle(step: ScoringStep, fname: Fname): string {
  switch (step.name) {
    case "complete_sets":
      return "Complete sets (fewest followers among the three factions in court; most wins)";
    case "last_play":
      return "Most recent action card played (latest wins; never played loses)";
    case "rank_1_followers":
      return `Most followers of the rank 1 faction${step.faction === null ? "" : ` (${fname(step.faction)})`}`;
    case "rank_2_followers":
      return `Most followers of the rank 2 faction${step.faction === null ? "" : ` (${fname(step.faction)})`}`;
    case "hand_emptied":
      return "Emptied hand earliest (lowest wins; never emptied loses)";
    default:
      return step.name.replace(/_/g, " ");
  }
}

function valueText(step: ScoringStep, p: number): string {
  const v = step.values?.[p] ?? null;
  if (v === null) return "never";
  if (step.name === "last_play") return `play ${v}`;
  if (step.name === "hand_emptied") return `at play ${v}`;
  return String(v);
}

function Step({
  step,
  fname,
  winners,
  isLast,
}: {
  step: ScoringStep;
  fname: Fname;
  winners: number[];
  isLast: boolean;
}) {
  const head = (
    <th scope="row">
      {step.name.replace(/_/g, " ")}
      <br />
      <small>{stepTitle(step, fname)}</small>
    </th>
  );
  if (step.skipped) {
    return (
      <tr>
        {head}
        <td>-</td>
        <td>skipped (rank 2 faction is undefined, R-403)</td>
      </tr>
    );
  }
  const before = step.tied_before ?? [];
  const remaining = step.remaining ?? [];
  const applied = before.length > 1;
  const shared = isLast && remaining.length > 1 && remaining.every((p) => winners.includes(p));
  let outcome: string;
  if (!applied) outcome = "not needed: already decided";
  else if (shared)
    outcome = `still tied: ${list(remaining)} share the win${step.name === "hand_emptied" ? " (nobody emptied their hand)" : ""}`;
  else if (remaining.length === 1) outcome = `${player(remaining[0]!)} decides`;
  else outcome = `still tied: ${list(remaining)}`;
  return (
    <tr>
      {head}
      <td>
        {applied
          ? before.map((p) => `${player(p)} ${valueText(step, p)}`).join(", ")
          : `${list(before)} only`}
      </td>
      <td style={remaining.length && remaining.every((p) => winners.includes(p)) && applied ? { fontWeight: "bold" } : undefined}>
        {outcome}
      </td>
    </tr>
  );
}

/** End-of-game result: winners, outcome type, region control, faction ranking and tiebreak steps. */
export default function ScoringPanel({ v, fname }: { v: KidView; fname: Fname }) {
  const sc = v.scoring;
  const winners = v.winners ?? sc?.winners ?? [];
  const lastApplied = sc ? sc.steps.map((s) => !s.skipped).lastIndexOf(true) : -1;
  return (
    <section aria-label="Result">
      <h3>Result</h3>
      <p
        aria-label="Winners"
        style={{ background: "#fff3b0", color: "#222", padding: "0.4em 0.6em", fontWeight: "bold" }}
      >
        Winner(s): {list(winners)}{winners.length > 1 && " (shared win)"}
      </p>
      {v.returns && (
        <table aria-label="Scores">
          <thead>
            <tr>
              <th scope="col">Player</th>
              <th scope="col">Score</th>
            </tr>
          </thead>
          <tbody>
            {v.returns.map((r, p) => (
              <tr key={p} style={winners.includes(p) ? { fontWeight: "bold", background: "#fff3b0", color: "#222" } : undefined}>
                <th scope="row">{player(p)}</th>
                <td>{r}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {sc && (
        <>
          <h4>
            Scoring breakdown ({sc.mode === "invasion" ? "invasion: three unstable regions" : "coronation: eight struggles resolved"})
          </h4>
          {sc.mode === "coronation" && sc.regions_controlled && (
            <table aria-label="Region control">
              <thead>
                <tr>
                  <th scope="col">Faction</th>
                  <th scope="col">Regions controlled</th>
                  <th scope="col">Recent win</th>
                </tr>
              </thead>
              <tbody>
                {sc.regions_controlled.map((n, f) => {
                  const rw = sc.recent_win?.[f];
                  return (
                    <tr key={f}>
                      <th scope="row">{fname(f)}</th>
                      <td>{n}</td>
                      <td>{rw === undefined ? "-" : rw < 0 ? "never" : `struggle ${rw}`}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
          {sc.recent_win && (
            <>
              <p>
                Recent win:{" "}
                {sc.recent_win
                  .map((n, f) => `${fname(f)} ${n < 0 ? "never" : `struggle ${n}`}`)
                  .join(", ")}
              </p>
              <p>
                <small>
                  Recent win = the number of the power struggle in which a faction most recently
                  took control; never = no win. Breaks ties between factions controlling equal
                  numbers of regions (later win ranks higher).
                </small>
              </p>
            </>
          )}
          {sc.faction_ranking && (
            <p>
              Faction ranking (most regions, then most recent win): {rankingText(sc.faction_ranking, fname)}
            </p>
          )}
          <table aria-label="Scoring steps">
            <thead>
              <tr>
                <th scope="col">Step</th>
                <th scope="col">Compared</th>
                <th scope="col">Outcome</th>
              </tr>
            </thead>
            <tbody>
              {sc.steps.map((s, i) => (
                <Step key={i} step={s} fname={fname} winners={winners} isLast={i === lastApplied} />
              ))}
            </tbody>
          </table>
        </>
      )}
    </section>
  );
}
