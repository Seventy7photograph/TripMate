// 文件说明：Playwright 浏览器冒烟测试：trips.spec。
import { expect, test } from "@playwright/test";

test("user can create, refresh, edit and archive a trip", async ({ page }) => {
  const email = `trip-e2e-${Date.now()}@example.com`;

  await page.goto("/register");
  await page.getByLabel("称呼").fill("Trip E2E Traveler");
  await page.getByLabel("邮箱").fill(email);
  await page.getByLabel("密码", { exact: true }).fill("correct-horse-battery-staple");
  await page.getByLabel("确认密码").fill("correct-horse-battery-staple");
  await page.getByRole("button", { name: "创建账号" }).click();

  await page.getByRole("link", { name: "行程" }).first().click();
  await expect(page.getByRole("heading", { name: "旅行计划" })).toBeVisible();

  await page.getByRole("link", { name: "新建旅行" }).first().click();
  await page.getByLabel("目的地").fill("Chongqing");
  await page.getByLabel("出发地").fill("Shanghai");
  await page.getByLabel("开始日期").fill("2026-12-01");
  await page.getByLabel("结束日期").fill("2026-12-03");
  await page.getByLabel("出行人数").fill("2");
  await page.getByLabel("预算 (CNY)").fill("5000");
  await page.getByLabel("兴趣").fill("food, citywalk");
  await page.getByRole("button", { name: "创建旅行" }).click();

  await expect(page.getByRole("heading", { name: "Chongqing" })).toBeVisible();
  await expect(page.getByText("版本 1")).toBeVisible();

  await page.reload();
  await expect(page.getByRole("heading", { name: "Chongqing" })).toBeVisible();

  await page.getByLabel("目的地").fill("Chengdu");
  await page.getByRole("button", { name: "保存旅行" }).click();
  await expect(page.getByText("旅行需求已保存")).toBeVisible();
  await expect(page.getByText("版本 2")).toBeVisible();

  await page.getByRole("button", { name: "删除计划" }).click();
  await expect(
    page.getByRole("dialog", { name: "删除这份旅行计划？" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "确认删除" }).click();
  await expect(page.getByRole("heading", { name: "旅行计划" })).toBeVisible();
  await expect(page.getByText("还没有旅行计划")).toBeVisible();
});
