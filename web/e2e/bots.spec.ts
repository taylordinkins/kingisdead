import { expect, type Page, test } from "@playwright/test";

async function newGame(page: Page, botValue: string, seed: string) {
  await page.goto("/");
  await page.getByLabel("Players").selectOption("2");
  await page.getByLabel("Seat 0").selectOption("human");
  await page.getByLabel("Seat 1").selectOption(botValue);
  await page.getByLabel("Seed (optional)").fill(seed);
  await page.getByRole("button", { name: "Create game" }).click();
  await expect(page.getByText(/^Game \S+ · seats/)).toBeVisible();
}

async function playVsBot(page: Page, botValue: string, thinking: RegExp) {
  test.setTimeout(90_000);
  await newGame(page, botValue, "11");
  const log = page.getByLabel("Action log");
  const list = page.getByRole("list", { name: "Legal actions" }).getByRole("button").and(page.locator(":enabled"));
  let sawThinking = false;
  let humanMoves = 0;
  for (let i = 0; i < 40 && humanMoves < 4; i++) {
    if (await page.getByLabel("Game over").isVisible()) break;
    if (await list.count()) {
      const before = await log.innerText();
      await list.first().click({ timeout: 2_000 }).catch(() => {});
      await expect(async () => {
        expect(await log.innerText()).not.toBe(before);
      }).toPass({ timeout: 5_000 });
      humanMoves++;
    }
    // Wait for the bot to reply: the human regains the move (or the game ends).
    for (let j = 0; j < 100; j++) {
      if (await page.getByText(thinking).isVisible()) sawThinking = true;
      if ((await list.count()) > 0 || (await page.getByLabel("Game over").isVisible())) break;
      await page.waitForTimeout(100);
    }
    await expect(page.getByText(/Bot error/)).toHaveCount(0);
  }
  expect(humanMoves).toBeGreaterThanOrEqual(3);
  // Bot seat must have acted: log has entries from P1.
  expect(await log.innerText()).toMatch(/P1/);
  await expect(page.getByText(/Bot error/)).toHaveCount(0);
  return sawThinking;
}

test("human vs heuristic bot", async ({ page }) => {
  await playVsBot(page, "heuristic", /Heuristic \(P1\) is thinking/);
});

test("human vs MCTS Easy (mcts:20)", async ({ page }) => {
  await playVsBot(page, "mcts:20", /MCTS Easy \(P1\) is thinking/);
});
