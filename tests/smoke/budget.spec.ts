// 文件说明：Playwright 浏览器冒烟测试：budget.spec。
import { expect, test } from "@playwright/test";

test("user can review estimated cost and add actual expenses", async ({ page }) => {
  const email = `budget-e2e-${Date.now()}@example.com`;

  await page.goto("/register");
  await page.getByLabel("称呼").fill("Budget E2E Traveler");
  await page.getByLabel("邮箱").fill(email);
  await page.getByLabel("密码", { exact: true }).fill("correct-horse-battery-staple");
  await page.getByLabel("确认密码").fill("correct-horse-battery-staple");
  await page.getByRole("button", { name: "创建账号" }).click();

  await page.getByRole("link", { name: "行程" }).first().click();
  await page.getByRole("link", { name: "新建旅行" }).first().click();
  await page.getByLabel("目的地").fill("Chongqing");
  await page.getByLabel("开始日期").fill("2026-12-01");
  await page.getByLabel("结束日期").fill("2026-12-01");
  await page.getByLabel("预算 (CNY)").fill("1000");
  await page.getByRole("button", { name: "创建旅行" }).click();
  await page.getByRole("link", { name: "编辑逐日行程" }).click();
  await page.getByRole("button", { name: "生成每日骨架" }).first().click();

  const addForm = page.getByTestId("itinerary-add-stop").first();
  await addForm.getByLabel("地点名称").fill("Hongya Cave");
  await addForm.getByLabel("预计花费").fill("100");
  await addForm.getByRole("button", { name: "添加地点" }).click();
  await expect(page.getByTestId("itinerary-stop")).toHaveCount(1);

  await page.getByRole("link", { name: "预算与支出" }).first().click();
  await expect(page.getByRole("heading", { name: "预算与支出" })).toBeVisible();
  await expect(page.getByTestId("budget-estimated")).toHaveText("¥100");

  await page.getByLabel("支出类别").selectOption("food");
  await page.getByLabel("金额 (CNY)").fill("250.50");
  await page.getByLabel("支出日期").fill("2026-12-01");
  await page.getByLabel("备注").fill("Lunch");
  await page.getByRole("button", { name: "记录支出" }).click();

  await expect(page.getByTestId("budget-actual")).toHaveText("¥250.50");
  await expect(page.getByTestId("budget-remaining")).toHaveText("剩余 ¥749.50");
});
