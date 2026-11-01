import { expect, type Page, test } from "@playwright/test";

const REGION = ".kid-region[role=button]";
const HAND_CARD = '[role=group][aria-label$=" hand"] button';
const CHOOSER = '[data-testid="region-chooser"]';

async function newGame(page: Page, seed: string) {
  await page.goto("/");
  await page.getByLabel("Players").selectOption("2");
  await page.getByLabel("Seat 0").selectOption("human");
  await page.getByLabel("Seat 1").selectOption("random");
  await page.getByLabel("Seed (optional)").fill(seed);
  await page.getByRole("button", { name: "Create game" }).click();
  await expect(page.getByText(/^Game \S+ · seats/)).toBeVisible();
}

/**
 * One click on the board: chooser option, else hand card, else region, else the action list
 * fallback. Returns the channel used, or null if nothing was clickable (bot's turn / ended).
 */
async function clickSomething(page: Page, n: number): Promise<string | null> {
  const tries: [string, ReturnType<Page["locator"]>][] = [
    ["chooser", page.locator(`${CHOOSER} button:not([aria-label="Cancel choice"])`)],
    // alternate so both hand-card and region clicks are exercised
    ...(n % 2 === 0
      ? ([
          ["card", page.locator(HAND_CARD)],
          ["region", page.locator(REGION)],
        ] as [string, ReturnType<Page["locator"]>][])
      : ([
          ["region", page.locator(REGION)],
          ["card", page.locator(HAND_CARD)],
        ] as [string, ReturnType<Page["locator"]>][])),
    ["list", page.getByRole("list", { name: "Legal actions" }).getByRole("button").and(page.locator(":enabled"))],
  ];
  for (const [name, loc] of tries) {
    if ((await loc.count()) > 0) {
      const ok = await loc
        .first()
        .click({ timeout: 2_000 })
        .then(() => true)
        .catch(() => false);
      if (ok) return name;
    }
  }
  return null;
}

test("click-through game on the board vs random bot", async ({ page }) => {
  test.setTimeout(300_000);
  await newGame(page, "7");
  const board = page.getByLabel("King is Dead board");
  await expect(board).toBeVisible();
  await expect(page.locator(".kid-region").first()).toBeVisible();

  const over = page.getByLabel("Game over");
  const used = new Set<string>();
  const log = page.getByLabel("Action log");
  let progressed = false;
  let backChecked = false;
  let moves = 0;
  for (let i = 0; i < 800 && moves < 400; i++) {
    if (await over.isVisible()) break;
    const before = await log.innerText();
    const via = await clickSomething(page, i);
    if (!via) {
      await page.waitForTimeout(150);
      continue;
    }
    used.add(via);
    if (via === "chooser" || (via === "region" && (await page.locator(CHOOSER).count()) > 0)) continue;
    moves++;
    await expect(async () => {
      expect(await log.innerText()).not.toBe(before);
    }).toPass({ timeout: 5_000 }).catch(() => {});
    if (!progressed && (await log.innerText()) !== before) progressed = true;

    if (moves === 6 && !backChecked) {
      // Back undoes to the previous human decision point: history length must shrink.
      await expect(page.getByText(/is thinking/)).toHaveCount(0, { timeout: 10_000 });
      const len = (await log.innerText()).length;
      await page.getByRole("button", { name: "Back" }).click();
      await expect(async () => {
        expect((await log.innerText()).length).toBeLessThan(len);
      }).toPass({ timeout: 5_000 });
      backChecked = true;
    }
  }
  expect(progressed).toBe(true);
  expect(backChecked).toBe(true);
  // Board interactions: at least region or hand-card clicks (not only the list fallback).
  expect(used.has("region") || used.has("card")).toBe(true);

  await expect(over).toBeVisible();
  await expect(over.getByText(/^Winner\(s\): P\d/)).toBeVisible();
  const result = page.getByLabel("Result");
  await expect(result).toBeVisible();
  await expect(result.getByRole("table", { name: "Scores" })).toBeVisible();
});

test("editor: load example, start playing vs random bot", async ({ page }) => {
  await page.goto("/#/editor");
  await page.getByLabel("Load example").selectOption({ label: "Basic 2-player setup" });
  await expect(page.getByRole("status").filter({ hasText: /^Valid/ })).toBeVisible();
  await page.getByLabel("Seat 0").selectOption("human");
  await page.getByLabel("Seat 1").selectOption("random");
  await page.getByRole("button", { name: "Start playing" }).click();
  await expect(page.getByText(/^Game \S+ · seats/)).toBeVisible();
  await expect(page.getByLabel("King is Dead board")).toBeVisible();
  await expect(page.locator(".kid-region").first()).toBeVisible();
});

test("editor: pasted JSON import validates", async ({ page }) => {
  await page.goto("/#/editor");
  await page.getByLabel("Load example").selectOption({ label: "Coronation tiebreak (state)" });
  const json = await page.getByLabel("Scenario JSON").inputValue();
  await page.reload();
  await page.getByLabel("Paste JSON").fill(json);
  await page.getByRole("button", { name: "Import JSON" }).click();
  await expect(page.getByRole("status").filter({ hasText: /^Valid/ })).toBeVisible();
});

test.describe("layout at 1280x800", () => {
  test.use({ viewport: { width: 1280, height: 800 } });

  test("Your move panel and the map track are visible without page scroll", async ({ page }) => {
    await newGame(page, "7");
    const panel = page.getByRole("region", { name: "Your move" });
    await expect(panel).toBeVisible();
    await expect(panel).toContainText(/^Your move: choose/);
    const inViewport = async (loc: ReturnType<Page["locator"]>) => {
      const box = await loc.boundingBox();
      expect(box).not.toBeNull();
      expect(box!.y).toBeGreaterThanOrEqual(0);
      expect(box!.y + box!.height).toBeLessThanOrEqual(800);
    };
    await inViewport(panel);
    await inViewport(page.getByRole("group", { name: "King is Dead map" }));
    await inViewport(page.getByRole("group", { name: "Supply" }));
    expect(await page.evaluate(() => document.documentElement.scrollHeight)).toBeLessThanOrEqual(800);
  });
});

test.describe("narrow layout", () => {
  test.use({ viewport: { width: 600, height: 900 } });

  test("tabs switch between Play, Board and Log", async ({ page }) => {
    await newGame(page, "7");
    const move = page.getByRole("region", { name: "Your move" });
    const map = page.getByRole("group", { name: "King is Dead map" });
    const log = page.getByLabel("Action log");
    await expect(move).toBeVisible();
    await expect(map).toBeHidden();
    await page.getByRole("tab", { name: "Board" }).click();
    await expect(map).toBeVisible();
    await expect(move).toBeHidden();
    await page.getByRole("tab", { name: "Log" }).click();
    await expect(log).toBeVisible();
    await expect(map).toBeHidden();
    await page.getByRole("tab", { name: "Play" }).click();
    await expect(move).toBeVisible();
  });
});
