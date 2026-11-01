import { render, screen } from "@testing-library/react";
import ActionLog, { groupHistory } from "./ActionLog";

const e = (index: number, actor: number | null, label = `L${index}`) => ({ index, actor, id: index, label });

describe("ActionLog", () => {
  const hist = [e(0, null), e(1, null), e(2, null), e(3, 0, "Play Spear"), e(4, 1, "Pass")];

  it("groups leading chance draws into one expandable row", () => {
    render(<ActionLog history={hist} />);
    const log = screen.getByRole("list", { name: "Action log" });
    expect(log).toHaveTextContent("Setup (3 random draws)");
    expect(log.querySelectorAll("details")).toHaveLength(1);
  });

  it("numbers player actions like Rewind and marks the latest", () => {
    render(<ActionLog history={hist} actorStyle={() => ({ fill: "#123456", ink: "#fff" })} />);
    expect(screen.getByText("P1:")).toHaveStyle({ background: "#123456" });
    const current = document.querySelector('[aria-current="step"]')!;
    expect(current).toHaveTextContent("Pass");
    expect(current).toHaveTextContent("(action 2)");
  });

  it("groups mid-game chance runs separately", () => {
    const g = groupHistory([e(0, 0), e(1, null), e(2, null), e(3, 1)]);
    expect(g.map((i) => i.kind)).toEqual(["action", "chance", "action"]);
  });
});
