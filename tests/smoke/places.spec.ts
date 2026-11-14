// 文件说明：Playwright 浏览器冒烟测试：places.spec。
import { expect, test } from "@playwright/test";

test("user can search mock places and inspect source metadata", async ({ page }) => {
  const email = `places-e2e-${Date.now()}@example.com`;

  await page.goto("/register");
  await page.getByLabel("称呼").fill("Places E2E Traveler");
  await page.getByLabel("邮箱").fill(email);
  await page.getByLabel("密码", { exact: true }).fill("correct-horse-battery-staple");
  await page.getByLabel("确认密码").fill("correct-horse-battery-staple");
  await page.getByRole("button", { name: "创建账号" }).click();

  await page.getByRole("link", { name: "探索" }).first().click();
  await expect(page.getByRole("heading", { name: "目的地与地点" })).toBeVisible();
  await expect(page.getByText("Mock 数据")).toBeVisible();
  await expect(page.getByLabel("数量")).toHaveValue("10");

  await page.getByLabel("搜索地点").fill("洪崖");
  await page.getByLabel("城市").fill("重庆");

  await expect(page.getByText("洪崖洞民俗风貌区")).toBeVisible();
  await expect(page.getByText(/Mock · 查询于/).first()).toBeVisible();
  await expect(page.getByTestId("places-map")).toHaveAttribute(
    "data-map-ready",
    "true",
  );
  await expect(page.locator(".place-map-marker")).toHaveCount(1);
  for (const width of [1180, 900, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await expect(page.getByTestId("places-map")).toBeVisible();
    const mapBox = await page.getByTestId("places-map").boundingBox();
    expect(mapBox?.width ?? 0).toBeGreaterThan(250);
  }
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(
    await page.evaluate(() => window.innerWidth),
  );
  await page.getByRole("button", { name: "查看 洪崖洞民俗风貌区 详情" }).click();
  await expect(
    page
      .locator(".place-result__detail")
      .getByText("渝中区 · 嘉陵江滨江路88号"),
  ).toBeVisible();
});
