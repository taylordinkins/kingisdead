import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Editor, { STORAGE_KEY } from "./Editor";
import { EXAMPLES } from "./examples";
import { fromScenarioJson, toScenarioJson } from "./json";

const POST = vi.fn();
vi.mock("../api/client", () => ({ api: { POST: (...a: unknown[]) => POST(...a), GET: vi.fn() } }));

beforeEach(() => {
  POST.mockReset();
  window.localStorage.clear();
});

const loadExample = (i: number) => fireEvent.change(screen.getByLabelText("Load example"), { target: { value: String(i) } });

describe("Editor", () => {
  it("renders the editor with issues for a blank setup", () => {
    render(<Editor onCreated={vi.fn()} onExit={vi.fn()} />);
    expect(screen.getByRole("heading", { name: "Setup editor" })).toBeInTheDocument();
    expect(screen.getByLabelText("Editor map")).toBeInTheDocument();
    expect(within(screen.getByLabelText("Issues")).getAllByText("V11").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Start playing" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Check with server" })).toBeDisabled();
  });

  it("stepper updates the model; issues appear and clear", () => {
    render(<Editor onCreated={vi.fn()} onExit={vi.fn()} />);
    loadExample(0);
    expect(screen.getByRole("status")).toHaveTextContent("Valid");
    expect(screen.getByRole("button", { name: "Start playing" })).toBeEnabled();
    fireEvent.click(screen.getByRole("button", { name: "Increase S in Moray" }));
    expect(screen.getByLabelText("S in Moray")).toHaveTextContent("3");
    expect(screen.getByLabelText("Issues")).toBeInTheDocument();
    expect(screen.getByTestId("map-Moray")).toHaveAttribute("data-bad", "true");
    expect(screen.getByRole("button", { name: "Start playing" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Decrease S in Moray" }));
    expect(screen.getByRole("status")).toHaveTextContent("Valid");
    expect(screen.getByTestId("map-Moray")).not.toHaveAttribute("data-bad");
  });

  it("moves region cards on the track", () => {
    render(<Editor onCreated={vi.fn()} onExit={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Move Strathclyde card earlier" }));
    expect(within(screen.getByTestId("slot-1")).getByText("Strathclyde")).toBeInTheDocument();
  });

  it("shows state-only sections for the state kind", () => {
    render(<Editor onCreated={vi.fn()} onExit={vi.fn()} />);
    expect(screen.queryByText("Hands")).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Kind"), { target: { value: "state" } });
    expect(screen.getByText("Hands")).toBeInTheDocument();
    expect(screen.getByLabelText("To play")).toBeInTheDocument();
  });

  it("shows the path and message of an import error", () => {
    render(<Editor onCreated={vi.fn()} onExit={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("Paste JSON"), { target: { value: JSON.stringify({ format: 1, kind: "setup", players: 5 }) } });
    fireEvent.click(screen.getByRole("button", { name: "Import JSON" }));
    expect(screen.getByRole("alert")).toHaveTextContent(/Import error: .*players/);
    fireEvent.change(screen.getByLabelText("Paste JSON"), { target: { value: "{nope" } });
    fireEvent.click(screen.getByRole("button", { name: "Import JSON" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Not valid JSON");
  });

  it("exports JSON equal to toScenarioJson and persists to localStorage", () => {
    render(<Editor onCreated={vi.fn()} onExit={vi.fn()} />);
    loadExample(1);
    const expected = toScenarioJson(fromScenarioJson(EXAMPLES[1]!.json));
    const text = (screen.getByLabelText("Scenario JSON") as HTMLTextAreaElement).value;
    expect(JSON.parse(text)).toEqual(expected);
    expect(JSON.parse(window.localStorage.getItem(STORAGE_KEY)!)).toEqual(expected);
  });

  it("restores the stored model on mount", () => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(toScenarioJson(fromScenarioJson(EXAMPLES[0]!.json))));
    render(<Editor onCreated={vi.fn()} onExit={vi.fn()} />);
    expect(screen.getByRole("status")).toHaveTextContent("Valid");
  });

  it("start playing posts the scenario and navigates", async () => {
    POST.mockResolvedValue({ data: { id: "g42" } });
    const onCreated = vi.fn();
    render(<Editor onCreated={onCreated} onExit={vi.fn()} />);
    loadExample(0);
    fireEvent.change(screen.getByLabelText("Seat 2"), { target: { value: "random" } });
    fireEvent.click(screen.getByRole("button", { name: "Start playing" }));
    await waitFor(() => expect(onCreated).toHaveBeenCalledWith("g42"));
    const [path, init] = POST.mock.calls[0] as [string, { body: Record<string, unknown> }];
    expect(path).toBe("/api/games");
    expect(init.body.scenario).toEqual(toScenarioJson(fromScenarioJson(EXAMPLES[0]!.json)));
    expect(init.body.seats).toEqual(["human", "random"]);
  });

  it("surfaces the server 422 detail", async () => {
    POST.mockResolvedValue({ error: { detail: "V4: closed regions bad" } });
    render(<Editor onCreated={vi.fn()} onExit={vi.fn()} />);
    loadExample(0);
    fireEvent.click(screen.getByRole("button", { name: "Start playing" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("V4: closed regions bad");
  });
});
