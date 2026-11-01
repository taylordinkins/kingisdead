import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import Tip from "../../shell/Tip";
import { CARD_TEXT, cardText } from "./cardText";

describe("card text", () => {
  it("has text for all 7 cards", () => {
    for (let id = 1; id <= 7; id++) expect(cardText(id)?.length).toBeGreaterThan(20);
    expect(Object.keys(CARD_TEXT)).toHaveLength(7);
  });
  it("tooltip shows on hover and focus, hides on leave and Escape", () => {
    render(
      <Tip text="Does a thing">
        <button type="button">Play X</button>
      </Tip>,
    );
    const b = screen.getByRole("button", { name: "Play X" });
    const wrap = b.parentElement as HTMLElement;
    expect(screen.queryByRole("tooltip")).toBeNull();
    fireEvent.mouseEnter(wrap);
    expect(screen.getByRole("tooltip").textContent).toBe("Does a thing");
    expect(b.getAttribute("aria-describedby")).toBe(screen.getByRole("tooltip").id);
    fireEvent.mouseLeave(wrap);
    expect(screen.queryByRole("tooltip")).toBeNull();
    fireEvent.focus(b);
    expect(screen.getByRole("tooltip")).toBeTruthy();
    fireEvent.keyDown(b, { key: "Escape" });
    expect(screen.queryByRole("tooltip")).toBeNull();
  });
});
