import type { ReactNode } from "react";
import type { GameView } from "../../shell/useGame";
import { parseKidView, type KidView, type ScoringStep } from "./types";

type Fname = (f: number | null) => string;
const player = (p: number | null): string => (p === null ? "none" : `P${p}`);
const list = (xs: number[] | undefined): string =>
  xs && xs.length ? xs.map(player).join(", ") : "none";
const words = (s: string): string => s.replace(/_/g, " ");

function ScoringStepRow({ step, fname }: { step: ScoringStep; fname: Fname }) {
  return (
    <tr>
      <th scope="row">{words(step.name)}</th>
      {step.skipped ? (
        <td colSpan={3}>skipped</td>
      ) : (
        <>
          <td>{step.faction === null ? "-" : fname(step.faction)}</td>
          <td>{(step.values ?? []).map((v, p) => `${player(p)}: ${v ?? "-"}`).join(", ")}</td>
          <td>{list(step.remaining)}</td>
        </>
      )}
    </tr>
  );
}

function Header({ v, fname, cardName }: { v: KidView; fname: Fname; cardName: (id: string) => string }): ReactNode {
  const region = (r: number): string => v.regions[r]?.name ?? String(r);
  const p = v.pending;
  return (
    <dl aria-label="Turn status">
      <dt>Stage</dt>
      <dd>{words(v.stage)}</dd>
      <dt>Phase</dt>
      <dd>{words(v.phase)}</dd>
      <dt>Current player</dt>
      <dd>
        {v.is_terminal ? "game over" : v.current_player === null ? "chance" : player(v.current_player)}
      </dd>
      <dt>Consecutive passes</dt>
      <dd>{v.consecutive_passes}</dd>
      {p.card != null && (
        <>
          <dt>Pending card</dt>
          <dd>{cardName(String(p.card))}</dd>
        </>
      )}
      {p.assemble_faction != null && (
        <>
          <dt>Assembling</dt>
          <dd>{fname(p.assemble_faction)}</dd>
        </>
      )}
      {p.neg_first != null && (
        <>
          <dt>Negotiation first region</dt>
          <dd>{region(p.neg_first)}</dd>
        </>
      )}
      {p.neg_second != null && (
        <>
          <dt>Negotiation second region</dt>
          <dd>{region(p.neg_second)}</dd>
        </>
      )}
    </dl>
  );
}

export function KidBoard({ v }: { v: KidView }) {
  const fname: Fname = (f) =>
    f === null ? "none" : (v.faction_names[f] ?? `Faction ${f}`);
  const cardName = (id: string): string => v.card_names[id] ?? `Card ${id}`;
  const factions = v.faction_names;
  const regionName = (r: number | null): string =>
    r === null ? "(not placed)" : (v.regions[r]?.name ?? `Region ${r}`);
  const players = Array.from({ length: v.num_players }, (_, p) => p);
  const sc = v.scoring;
  return (
    <div aria-label="King is Dead board">
      <p>
        Regions resolved: {v.struggles_resolved} of {v.track.length}
      </p>
      <Header v={v} fname={fname} cardName={cardName} />

      <h3>Power struggle track</h3>
      <table aria-label="Region track">
        <thead>
          <tr>
            <th scope="col">Slot</th>
            <th scope="col">Region</th>
            <th scope="col">Status</th>
            <th scope="col">Negotiation discs</th>
          </tr>
        </thead>
        <tbody>
          {v.track.map((t) => (
            <tr key={t.slot}>
              <th scope="row">{t.slot + 1}</th>
              <td>{regionName(t.region)}</td>
              <td>{t.face_down ? "resolved" : "pending"}</td>
              <td>{list(t.discs)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3>Regions</h3>
      <table aria-label="Regions">
        <thead>
          <tr>
            <th scope="col">Region</th>
            {factions.map((f) => (
              <th scope="col" key={f}>
                {f}
              </th>
            ))}
            <th scope="col">State</th>
            <th scope="col">Controller</th>
          </tr>
        </thead>
        <tbody>
          {v.regions.map((r) => (
            <tr key={r.region}>
              <th scope="row">{r.name}</th>
              {factions.map((f, i) => (
                <td key={f}>{r.followers[i] ?? 0}</td>
              ))}
              <td>{r.state}</td>
              <td>{r.state === "controlled" ? fname(r.controller) : "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3>Courts and supply</h3>
      <table aria-label="Courts">
        <thead>
          <tr>
            <th scope="col">Followers</th>
            {factions.map((f) => (
              <th scope="col" key={f}>
                {f}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {players.map((p) => (
            <tr key={p}>
              <th scope="row">{`P${p} court`}</th>
              {factions.map((f, i) => (
                <td key={f}>{v.courts[p]?.[i] ?? 0}</td>
              ))}
            </tr>
          ))}
          <tr>
            <th scope="row">Supply</th>
            {factions.map((f, i) => (
              <td key={f}>{v.supply[i] ?? 0}</td>
            ))}
          </tr>
        </tbody>
      </table>

      <h3>Hands</h3>
      <table aria-label="Hands">
        <tbody>
          {players.map((p) => {
            const hand = Object.entries(v.hands[p] ?? {}).filter(([, n]) => n > 0);
            const disc = v.negotiation_discs[p];
            return (
              <tr key={p}>
                <th scope="row">{`P${p}`}</th>
                <td>
                  {hand.length ? hand.map(([c, n]) => `${cardName(c)} x${n}`).join(", ") : "empty"}
                </td>
                <td>{disc == null ? "" : `disc on ${regionName(disc)}`}</td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {v.is_terminal && (
        <section aria-label="Result">
          <h3>Result</h3>
          {v.winners && <p>Winner(s): {list(v.winners)}</p>}
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
                  <tr key={p}>
                    <th scope="row">{player(p)}</th>
                    <td>{r}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {sc && (
            <>
              <h4>Scoring breakdown ({sc.mode})</h4>
              {sc.faction_ranking && (
                <p>Faction ranking: {sc.faction_ranking.map(fname).join(" > ")}</p>
              )}
              {sc.regions_controlled && (
                <p>
                  Regions controlled:{" "}
                  {sc.regions_controlled.map((n, f) => `${fname(f)} ${n}`).join(", ")}
                </p>
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
                      Recent win = the number of the power struggle in which a faction most
                      recently took control; never = no win. Breaks ties between factions
                      controlling equal numbers of regions (higher ranks first).
                    </small>
                  </p>
                </>
              )}
              <table aria-label="Scoring steps">
                <thead>
                  <tr>
                    <th scope="col">Step</th>
                    <th scope="col">Faction</th>
                    <th scope="col">Values</th>
                    <th scope="col">Remaining</th>
                  </tr>
                </thead>
                <tbody>
                  {sc.steps.map((s, i) => (
                    <ScoringStepRow key={i} step={s} fname={fname} />
                  ))}
                </tbody>
              </table>
            </>
          )}
        </section>
      )}
    </div>
  );
}

export default function Board({ game }: { game: GameView }) {
  let v: KidView;
  try {
    v = parseKidView(game.view);
  } catch (e) {
    return (
      <p role="alert">Cannot display board: {e instanceof Error ? e.message : "invalid view"}</p>
    );
  }
  return <KidBoard v={v} />;
}
