import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import App from "./App";

describe("App", () => {
  beforeEach(() => {
    window.location.hash = "";
  });

  it("renders the heading", () => {
    render(<App />);
    expect(screen.getByRole("heading", { name: "The King is Dead" })).toBeInTheDocument();
  });

  it("follows the hash between lobby and editor", async () => {
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: /set up a table/i }));
    const back = await screen.findByRole("button", { name: /back to lobby/i });
    expect(window.location.hash).toBe("#/editor");
    fireEvent.click(back);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /set up a table/i })).toBeInTheDocument(),
    );
    expect(screen.queryByRole("button", { name: /back to lobby/i })).toBeNull();
  });
});
