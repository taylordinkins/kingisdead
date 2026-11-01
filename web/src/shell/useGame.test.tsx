import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, vi } from "vitest";
import { rankingText } from "../games/king-is-dead/ranking";
import { useGame, type GameView } from "./useGame";

const GET = vi.fn();
const POST = vi.fn();
vi.mock("../api/client", () => ({
  api: { GET: (...a: unknown[]) => GET(...a), POST: (...a: unknown[]) => POST(...a) },
}));

const POLL = { fast: 20, slow: 20 };

function view(over: Partial<GameView> = {}): GameView {
  return {
    id: "g1",
    game: "test_game",
    seats: ["human", "random"],
    seat_types: ["human", "random"],
    seed: 1,
    bot_thinking: false,
    seat: 0,
    history_length: 0,
    history: [],
    dev_mode: false,
    current_player: 0,
    is_terminal: false,
    legal_actions: [{ id: 9, label: "Pass" }],
    returns: null,
    winners: null,
    view: {},
    ...over,
  };
}

beforeEach(() => {
  GET.mockReset();
  POST.mockReset();
});

const AUTO = { autoAdvanceForced: true, autoAdvanceDelay: 30 };
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

describe("auto-advance", () => {
  it("fires once on a single legal action", async () => {
    GET.mockResolvedValue({ data: view() });
    POST.mockResolvedValue({ data: view({ history_length: 1, current_player: 1 }) });
    const { result } = renderHook(() => useGame("g1", POLL, AUTO));
    await waitFor(() => expect(POST).toHaveBeenCalledTimes(1));
    expect(POST.mock.calls[0]![1].body).toEqual({ action: 9 });
    await waitFor(() => expect(result.current.autoNote).toContain("Pass"));
    await sleep(100);
    expect(POST).toHaveBeenCalledTimes(1);
  });

  it("does not loop when the state is unchanged after submit", async () => {
    GET.mockResolvedValue({ data: view() });
    POST.mockResolvedValue({ data: view() });
    renderHook(() => useGame("g1", POLL, AUTO));
    await waitFor(() => expect(POST).toHaveBeenCalledTimes(1));
    await sleep(150);
    expect(POST).toHaveBeenCalledTimes(1);
  });

  it("does not fire with several actions, off-turn, or when disabled", async () => {
    GET.mockResolvedValue({
      data: view({ legal_actions: [{ id: 1, label: "A" }, { id: 2, label: "B" }] }),
    });
    {
      const h = renderHook(() => useGame("g1", POLL, AUTO));
      await sleep(120);
      h.unmount();
    }
    expect(POST).not.toHaveBeenCalled();

    GET.mockResolvedValue({ data: view({ current_player: 1 }) });
    {
      const h = renderHook(() => useGame("g1", POLL, AUTO));
      await sleep(120);
      h.unmount();
    }
    expect(POST).not.toHaveBeenCalled();

    GET.mockResolvedValue({ data: view() });
    {
      const h = renderHook(() => useGame("g1", POLL, { autoAdvanceDelay: 30 }));
      await sleep(120);
      h.unmount();
    }
    expect(POST).not.toHaveBeenCalled();
  });

  it("is cancelled when state changes before the delay", async () => {
    GET.mockResolvedValueOnce({ data: view() });
    GET.mockResolvedValue({
      data: view({ history_length: 1, legal_actions: [{ id: 1, label: "A" }, { id: 2, label: "B" }] }),
    });
    renderHook(() => useGame("g1", POLL, { ...AUTO, autoAdvanceDelay: 60 }));
    await sleep(200);
    expect(POST).not.toHaveBeenCalled();
  });
});

describe("polling", () => {
  it("drops a stale poll response that finishes after a local mutation", async () => {
    let release: (v: unknown) => void = () => {};
    GET.mockResolvedValueOnce({ data: view({ legal_actions: [], history_length: 0 }) });
    const { result } = renderHook(() => useGame("g1", { fast: 10, slow: 10 }));
    await waitFor(() => expect(result.current.game).not.toBeNull());
    GET.mockReset();
    GET.mockReturnValue(new Promise((r) => (release = r)));
    POST.mockResolvedValue({ data: view({ history_length: 5, legal_actions: [] }) });
    await waitFor(() => expect(GET).toHaveBeenCalled());
    await act(async () => {
      await result.current.act(1);
    });
    expect(result.current.game?.history_length).toBe(5);
    await act(async () => {
      release({ data: view({ history_length: 0, legal_actions: [] }) });
      await sleep(5);
    });
    expect(result.current.game?.history_length).toBe(5);
  });

  it("keeps polling after repeated identical errors", async () => {
    GET.mockResolvedValueOnce({ data: view({ legal_actions: [] }) });
    const { result } = renderHook(() => useGame("g1", { fast: 10, slow: 10 }));
    await waitFor(() => expect(result.current.game).not.toBeNull());
    GET.mockReset();
    GET.mockRejectedValue(new Error("down"));
    await waitFor(() => expect(GET.mock.calls.length).toBeGreaterThanOrEqual(5));
    expect(result.current.error).toBe("down");
    GET.mockResolvedValue({ data: view({ history_length: 2, legal_actions: [] }) });
    await waitFor(() => expect(result.current.game?.history_length).toBe(2));
    expect(result.current.error).toBeNull();
  });
});

describe("rankingText (R-403)", () => {
  const name = (f: number | null) => (f === null ? "none" : ["Scots", "Welsh", "English"][f]!);
  it("joins fully defined rankings", () => {
    expect(rankingText([0, 2, 1], name)).toBe("Scots > English > Welsh");
  });
  it("words undefined ranks 2 and 3", () => {
    const t = rankingText([0, null, null], name);
    expect(t).toBe("Scots; ranks 2 and 3 undefined (tied factions control no regions)");
    expect(t).not.toContain("none");
  });
  it("words a single undefined rank", () => {
    expect(rankingText([0, 1, null], name)).toContain("rank 3 undefined");
  });
});
