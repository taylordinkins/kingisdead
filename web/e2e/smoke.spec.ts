import { expect, test } from "@playwright/test";

// Fixed seed so the game is reproducible.
const SEED = "1";

async function newGame(page: import("@playwright/test").Page) {
  await page.goto("/");
  await page.getByLabel("Players").selectOption("2");
  await page.getByLabel("Seat 1").selectOption("human");
  await page.getByLabel("Seat 2").selectOption("random");
  await page.getByLabel("Seed (optional)").fill(SEED);
  await page.getByRole("button", { name: "Create game" }).click();
  await expect(page.getByText(/^Game \S+ · seats/)).toBeVisible();
}

test("full game against the random bot reaches game over", async ({ page }) => {
  test.setTimeout(240_000);
  await newGame(page);
  const over = page.getByLabel("Game over");
  const buttons = page.getByRole("list", { name: "Legal actions" }).getByRole("button");
  let moves = 0;
  for (; moves < 500; moves++) {
    if (await over.isVisible()) break;
    const enabled = buttons.and(page.locator(":enabled")).first();
    try {
      await enabled.waitFor({ state: "visible", timeout: 500 });
    } catch {
      continue; // bot thinking or game just ended; re-check
    }
    await enabled.click({ timeout: 2_000 }).catch(() => {});
  }
  await expect(over).toBeVisible();
  expect(moves).toBeLessThan(500);
  await expect(over.getByText(/^Winner\(s\): P\d/)).toBeVisible();
  await expect(over.getByText(/^Scores: /)).toBeVisible();
});

test("report dialog submits and shows an id", async ({ page }) => {
  await newGame(page);
  await page.getByRole("button", { name: "Report a problem" }).click();
  const dialog = page.getByRole("dialog", { name: "Report a problem" });
  await dialog.getByLabel("Note").fill("e2e smoke report");
  await dialog.getByRole("button", { name: "Submit report" }).click();
  await expect(dialog.getByRole("status")).toContainText(/Report id: \S+/);
});
