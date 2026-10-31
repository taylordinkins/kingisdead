import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, vi } from "vitest";
import ImportButton from "./ImportButton";
import GameScreen from "./GameScreen";
import type { GameView } from "./useGame";

const GET = vi.fn();
const POST = vi.fn();
vi.mock("../api/client", () => ({
  api: { GET: (...a: unknown[]) => GET(...a), POST: (...a: unknown[]) => POST(...a) },
}));

const POLL = { fast: 10000, slow: 10000 };

function view(over: Partial<GameView> = {}): GameView {
  return {
    id: "g1",
    game: "test_game",
    seats: ["human", "random"],
    seat_types: ["human", "random"],
    seed: 1,
    bot_thinking: false,
    seat: 0,
    history_length: 2,
    history: [
      { index: 0, actor: null, id: 7, label: "Chance outcome 7" },
      { index: 1, actor: 0, id: 8, label: "Play Spear" },
    ],
    dev_mode: false,
    current_player: 0,
    is_terminal: false,
    legal_actions: [{ id: 3, label: "Play A" }],
    returns: null,
    winners: null,
    view: {},
    ...over,
  };
}

const EXPORT = { game: "king_is_dead", params: {}, seats: ["human", "random"], seed: 1, history: [7, 8] };

function mockGet(v: GameView) {
  GET.mockImplementation((path: string) =>
    Promise.resolve(path.endsWith("/export") ? { data: EXPORT } : { data: v }),
  );
}

beforeEach(() => {
  GET.mockReset();
  POST.mockReset();
});

describe("action log", () => {
  it("renders past actions", async () => {
    mockGet(view());
    render(<GameScreen gameId="g1" pollMs={POLL} />);
    const log = await screen.findByRole("list", { name: "Action log" });
    expect(log.querySelectorAll("li")).toHaveLength(2);
    expect(log).toHaveTextContent("Chance outcome 7");
    expect(log).toHaveTextContent("P0: Play Spear");
    expect(GET).not.toHaveBeenCalledWith("/api/games/{game_id}/export", expect.anything());
  });
});

describe("Back", () => {
  it("calls the back endpoint and shows the new state", async () => {
    mockGet(view());
    POST.mockResolvedValue({ data: view({ history_length: 0, legal_actions: [{ id: 5, label: "Earlier" }] }) });
    render(<GameScreen gameId="g1" pollMs={POLL} />);
    fireEvent.click(await screen.findByRole("button", { name: "Back" }));
    expect(POST).toHaveBeenCalledWith("/api/games/{game_id}/back", {
      params: { path: { game_id: "g1" } },
    });
    expect(await screen.findByRole("button", { name: "Earlier" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Back" })).toBeDisabled();
  });

  it("is disabled while a request is in flight", async () => {
    mockGet(view());
    let resolve: (v: unknown) => void = () => {};
    POST.mockReturnValue(new Promise((r) => (resolve = r)));
    render(<GameScreen gameId="g1" pollMs={POLL} />);
    fireEvent.click(await screen.findByRole("button", { name: "Back" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Back" })).toBeDisabled());
    resolve({ data: view() });
    await waitFor(() => expect(screen.getByRole("button", { name: "Back" })).toBeEnabled());
  });
});

describe("Rewind", () => {
  it("is hidden unless the server reports dev mode", async () => {
    mockGet(view());
    render(<GameScreen gameId="g1" pollMs={POLL} />);
    await screen.findByRole("button", { name: "Back" });
    expect(screen.queryByRole("button", { name: "Rewind" })).toBeNull();
  });

  it("posts the target when allowed", async () => {
    mockGet(view({ dev_mode: true }));
    POST.mockResolvedValue({ data: view({ dev_mode: true }) });
    render(<GameScreen gameId="g1" pollMs={POLL} />);
    fireEvent.change(await screen.findByLabelText(/Rewind to player action/), { target: { value: "1" } });
    fireEvent.click(screen.getByRole("button", { name: "Rewind" }));
    expect(POST).toHaveBeenCalledWith("/api/games/{game_id}/rewind", {
      params: { path: { game_id: "g1" } },
      body: { player_actions: 1 },
    });
  });
});

describe("Report dialog", () => {
  it("rejects an empty note, submits, and shows the id", async () => {
    mockGet(view());
    POST.mockResolvedValue({ data: { report_id: "r-123", path: "x" } });
    render(<GameScreen gameId="g1" pollMs={POLL} />);
    fireEvent.click(await screen.findByRole("button", { name: "Report a problem" }));
    fireEvent.click(screen.getByRole("button", { name: "Submit report" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Note is required");
    expect(POST).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText("Category"), { target: { value: "ui" } });
    fireEvent.change(screen.getByLabelText("Note"), { target: { value: "broken" } });
    fireEvent.click(screen.getByRole("button", { name: "Submit report" }));
    expect(await screen.findByRole("status")).toHaveTextContent("r-123");
    expect(POST).toHaveBeenCalledWith("/api/games/{game_id}/report", {
      params: { path: { game_id: "g1" } },
      body: { note: "broken", category: "ui" },
    });
  });

  it("shows a server error", async () => {
    mockGet(view());
    POST.mockResolvedValue({ error: { detail: "nope" } });
    render(<GameScreen gameId="g1" pollMs={POLL} />);
    fireEvent.click(await screen.findByRole("button", { name: "Report a problem" }));
    fireEvent.change(screen.getByLabelText("Note"), { target: { value: "x" } });
    fireEvent.click(screen.getByRole("button", { name: "Submit report" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("nope");
  });
});

describe("Export", () => {
  it("downloads kid-<id>.json", async () => {
    mockGet(view());
    const create = vi.fn(() => "blob:x");
    const revoke = vi.fn();
    Object.assign(URL, { createObjectURL: create, revokeObjectURL: revoke });
    const names: string[] = [];
    const click = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(function (this: HTMLAnchorElement) {
        names.push(this.download);
      });
    render(<GameScreen gameId="g1" pollMs={POLL} />);
    fireEvent.click(await screen.findByRole("button", { name: "Export replay" }));
    await waitFor(() => expect(names).toEqual(["kid-g1.json"]));
    expect(create).toHaveBeenCalled();
    click.mockRestore();
  });
});

describe("Import", () => {
  it("posts the file and navigates to the new game", async () => {
    POST.mockResolvedValue({ data: view({ id: "new1" }) });
    const onImported = vi.fn();
    render(<ImportButton onImported={onImported} />);
    const file = new File([JSON.stringify(EXPORT)], "kid-g1.json", { type: "application/json" });
    Object.defineProperty(file, "text", { value: () => Promise.resolve(JSON.stringify(EXPORT)) });
    fireEvent.change(screen.getByLabelText("Import replay"), { target: { files: [file] } });
    await waitFor(() => expect(onImported).toHaveBeenCalledWith("new1"));
    expect(POST).toHaveBeenCalledWith("/api/games/import", { body: EXPORT });
  });

  it("shows an error for bad files", async () => {
    POST.mockResolvedValue({ error: { detail: "invalid history" } });
    render(<ImportButton onImported={vi.fn()} />);
    const file = new File(["{}"], "a.json");
    Object.defineProperty(file, "text", { value: () => Promise.resolve("{}") });
    fireEvent.change(screen.getByLabelText("Import replay"), { target: { files: [file] } });
    expect(await screen.findByRole("alert")).toHaveTextContent("invalid history");
  });
});
