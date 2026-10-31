import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, vi } from "vitest";
import GameScreen from "./GameScreen";
import Lobby from "./Lobby";
import type { GameView } from "./useGame";

const GET = vi.fn();
const POST = vi.fn();
vi.mock("../api/client", () => ({ api: { GET: (...a: unknown[]) => GET(...a), POST: (...a: unknown[]) => POST(...a) } }));

const POLL = { fast: 20, slow: 20 };

function view(over: Partial<GameView> = {}, inner: Record<string, unknown> = {}): GameView {
  return {
    id: "g1",
    game: "king_is_dead",
    seats: ["human", "random"],
    seat_types: ["human", "random"],
    seed: 1,
    bot_thinking: false,
    seat: 0,
    history_length: 0,
    view: {
      current_player: 0,
      is_terminal: false,
      legal_actions: [
        { id: 3, label: "Play A" },
        { id: 4, label: "Pass" },
      ],
      ...inner,
    },
    ...over,
  };
}

beforeEach(() => {
  GET.mockReset();
  POST.mockReset();
});

describe("Lobby", () => {
  it("creates a game with chosen seats and seed", async () => {
    POST.mockResolvedValue({ data: view({ id: "abc" }) });
    const onCreated = vi.fn();
    render(<Lobby onCreated={onCreated} />);
    fireEvent.change(screen.getByLabelText("Seat 2"), { target: { value: "human" } });
    fireEvent.change(screen.getByLabelText(/Seed/), { target: { value: "42" } });
    fireEvent.click(screen.getByRole("button", { name: "Create game" }));
    await waitFor(() => expect(onCreated).toHaveBeenCalledWith("abc"));
    expect(POST).toHaveBeenCalledWith("/api/games", {
      body: {
        game: "king_is_dead",
        params: { num_players: 2 },
        seats: ["human", "human"],
        seed: 42,
      },
    });
  });

  it("shows an error when creation fails", async () => {
    POST.mockResolvedValue({ error: { detail: "bad seats" } });
    render(<Lobby onCreated={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Create game" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("bad seats");
  });
});

describe("GameScreen", () => {
  it("renders legal actions and posts the clicked one", async () => {
    GET.mockResolvedValue({ data: view() });
    POST.mockResolvedValue({ data: view({}, { current_player: 0, legal_actions: [{ id: 9, label: "Next" }] }) });
    render(<GameScreen gameId="g1" pollMs={{ fast: 10000, slow: 10000 }} />);
    fireEvent.click(await screen.findByRole("button", { name: "Play A" }));
    expect(POST).toHaveBeenCalledWith("/api/games/{game_id}/actions", {
      params: { path: { game_id: "g1" } },
      body: { action: 3 },
    });
    expect(await screen.findByRole("button", { name: "Next" })).toBeEnabled();
  });

  it("disables buttons while a request is in flight", async () => {
    GET.mockResolvedValue({ data: view() });
    let resolve: (v: unknown) => void = () => {};
    POST.mockReturnValue(new Promise((r) => (resolve = r)));
    render(<GameScreen gameId="g1" pollMs={{ fast: 10000, slow: 10000 }} />);
    fireEvent.click(await screen.findByRole("button", { name: "Play A" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Pass" })).toBeDisabled());
    await act(async () => resolve({ data: view() }));
    expect(screen.getByRole("button", { name: "Pass" })).toBeEnabled();
  });

  it("shows an error for a rejected action", async () => {
    GET.mockResolvedValue({ data: view() });
    POST.mockResolvedValue({ error: { detail: "action 3 is not legal" } });
    render(<GameScreen gameId="g1" pollMs={{ fast: 10000, slow: 10000 }} />);
    fireEvent.click(await screen.findByRole("button", { name: "Play A" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("action 3 is not legal");
    expect(screen.getByRole("button", { name: "Play A" })).toBeInTheDocument();
  });

  it("polls through bot thinking and stops at game over", async () => {
    GET.mockResolvedValueOnce({ data: view({ bot_thinking: true }, { current_player: 1 }) })
      .mockResolvedValueOnce({
        data: view({}, { current_player: null, is_terminal: true, legal_actions: [], returns: [1, -1], winners: [0] }),
      });
    render(<GameScreen gameId="g1" pollMs={POLL} />);
    expect(await screen.findByRole("status")).toHaveTextContent(/thinking/i);
    expect(screen.queryByRole("button", { name: "Play A" })).toBeNull();
    expect(await screen.findByText("Game over")).toBeInTheDocument();
    expect(screen.getByText(/Scores: 1, -1/)).toBeInTheDocument();
    expect(screen.queryByRole("status")).toBeNull();
    const calls = GET.mock.calls.length;
    await new Promise((r) => setTimeout(r, 100));
    expect(GET.mock.calls.length).toBe(calls);
  });

  it("stops polling on unmount", async () => {
    GET.mockResolvedValue({ data: view() });
    const { unmount } = render(<GameScreen gameId="g1" pollMs={POLL} />);
    await screen.findByRole("button", { name: "Pass" });
    unmount();
    const calls = GET.mock.calls.length;
    await new Promise((r) => setTimeout(r, 100));
    expect(GET.mock.calls.length).toBe(calls);
  });

  it("shows a load error without crashing", async () => {
    GET.mockResolvedValue({ error: { detail: "unknown game 'zz'" } });
    render(<GameScreen gameId="zz" pollMs={POLL} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("unknown game");
  });
});
