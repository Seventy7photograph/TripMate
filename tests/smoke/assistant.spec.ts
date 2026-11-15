// 文件说明：Playwright 浏览器冒烟测试：assistant.spec。
import { expect, test } from "@playwright/test";

test("user plans a trip through the home conversation", async ({ page }) => {
  const email = `home-agent-e2e-${Date.now()}@example.com`;

  await page.goto("/register");
  await page.getByLabel("称呼").fill("Home Agent Traveler");
  await page.getByLabel("邮箱").fill(email);
  await page.getByLabel("密码", { exact: true }).fill("correct-horse-battery-staple");
  await page.getByLabel("确认密码").fill("correct-horse-battery-staple");
  await page.getByRole("button", { name: "创建账号" }).click();

  await expect(
    page.getByRole("heading", { name: "新的故事，从哪里开始？" }),
  ).toBeVisible();
  await page
    .getByLabel("旅行问题或需求")
    .fill("2026年12月1日到12月3日，2个人从上海去重庆，喜欢美食。");
  await page.getByRole("button", { name: "开始规划" }).click();

  await expect(page.getByText("已生成")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole("link", { name: /旅行详情/ })).toBeVisible();
  await expect(page.getByRole("button", { name: "历史对话" })).toBeVisible();

  const detailRequests: string[] = [];
  page.on("request", (request) => {
    if (
      request.method() === "GET" &&
      /\/api\/v1\/conversations\/[^/?]+$/.test(request.url())
    ) {
      detailRequests.push(request.url());
    }
  });

  await page.evaluate(() => {
    (window as Window & { sawEmptyConversation?: boolean }).sawEmptyConversation =
      false;
    const observer = new MutationObserver(() => {
      if (document.querySelector(".home-hero")) {
        (window as Window & { sawEmptyConversation?: boolean }).sawEmptyConversation =
          true;
      }
    });
    observer.observe(document.body, { childList: true, subtree: true });
  });
  await page.getByRole("link", { name: "行程" }).first().click();
  await page.getByRole("link", { name: "对话" }).first().click();
  await expect(page.getByText("已生成")).toBeVisible({ timeout: 5_000 });
  await expect(
    page.getByRole("heading", { name: "新的故事，从哪里开始？" }),
  ).toHaveCount(0);
  expect(
    await page.evaluate(
      () =>
        (window as Window & { sawEmptyConversation?: boolean })
          .sawEmptyConversation,
    ),
  ).toBe(false);
  expect(detailRequests).toHaveLength(0);
  await page.reload();
  await expect(page.getByText("已生成")).toBeVisible();

  await page.getByRole("link", { name: /全屏地图/ }).click();
  await expect(page.locator(".map-route-sheet")).toBeVisible();
  await expect(page.getByRole("link", { name: "退出路书" })).toBeVisible();

  await page.setViewportSize({ width: 375, height: 900 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(375);
  await expect(page.locator(".app-menu-toggle")).toBeVisible();
});
