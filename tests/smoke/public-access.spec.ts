// 文件说明：Playwright 浏览器冒烟测试：public-access.spec。
import { expect, test } from "@playwright/test";

test("guests can view the conversation shell but protected actions redirect to login", async ({
  page,
}) => {
  await page.goto("/");

  await expect(
    page.getByRole("heading", { name: "新的故事，从哪里开始？" }),
  ).toBeVisible();
  await expect(page).toHaveTitle(/TripMate/);
  await expect(page.getByRole("button", { name: "历史对话" })).toBeVisible();
  await expect(page.locator('link[rel="icon"]')).toHaveAttribute(
    "href",
    /tripmate-mark/,
  );

  await page.getByLabel("旅行问题或需求").fill(
    "2026年12月1日到12月3日，2个人从上海去重庆，预算5000元。",
  );
  await expect(
    page.getByRole("heading", { name: "登录后开始规划" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "去登录" }).click();
  await expect(page).toHaveURL(/\/login\?/);
  expect(new URL(page.url()).searchParams.get("redirect")).toBe("/");
  await expect(page.getByRole("heading", { name: /把想去的地方/ })).toBeVisible();
  await expect(page.locator(".auth-backdrop-video")).toBeVisible();

  await page.goto("/trips");
  await expect(page).toHaveURL(/\/login\?/);
  expect(new URL(page.url()).searchParams.get("redirect")).toBe("/trips");
});

test("the top-right login action leads to the unified auth surface", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("link", { name: "登录" }).click();

  await expect(page).toHaveURL(/\/login/);
  await expect(page.getByLabel("邮箱")).toBeVisible();
  await expect(page.getByRole("link", { name: "创建账号" })).toBeVisible();
});
