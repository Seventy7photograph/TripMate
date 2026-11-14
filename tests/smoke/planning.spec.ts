// 文件说明：Playwright 浏览器冒烟测试：planning.spec。
import { expect, test } from "@playwright/test";

test("user can generate and open an applied LangGraph itinerary", async ({ page }) => {
  const email = `planning-e2e-${Date.now()}@example.com`;

  await page.goto("/register");
  await page.getByLabel("称呼").fill("Planning E2E Traveler");
  await page.getByLabel("邮箱").fill(email);
  await page.getByLabel("密码", { exact: true }).fill("correct-horse-battery-staple");
  await page.getByLabel("确认密码").fill("correct-horse-battery-staple");
  await page.getByRole("button", { name: "创建账号" }).click();

  await page.getByRole("link", { name: "行程" }).first().click();
  await page.getByRole("link", { name: "新建旅行" }).first().click();
  await page.getByLabel("目的地").fill("泉州");
  await page.getByLabel("开始日期").fill("2026-12-01");
  await page.getByLabel("结束日期").fill("2026-12-03");
  await page.getByLabel("必去地点").fill("开元寺");
  await page.getByRole("button", { name: "创建旅行" }).click();

  await page.getByRole("link", { name: "生成 AI 行程" }).click();
  await expect(page.getByRole("heading", { name: "生成逐日行程" })).toBeVisible();
  await expect(page.getByText("LangGraph Agent")).toBeVisible();
  await page.getByRole("button", { name: "生成行程" }).click();

  const draft = page.getByTestId("planner-draft");
  await expect(draft.getByText("规划完成", { exact: true })).toBeVisible();
  await expect(draft.getByTestId("draft-day")).toHaveCount(3);
  await expect(draft.getByText("泉州开元寺", { exact: true }).first()).toBeVisible();
  await expect(draft.getByText("洪崖洞民俗风貌区", { exact: true })).toHaveCount(0);
  await expect(page.getByText(/查看全部步骤/)).toBeVisible();
  await page.getByRole("link", { name: "打开逐日行程" }).click();
  await expect(page).toHaveURL(/\/trips\/.+\/itinerary$/);
  await expect(page.getByRole("heading", { name: "逐日行程" })).toBeVisible();
  await expect(page.getByText("泉州开元寺").first()).toBeVisible();
  await expect(page.getByText("3 天 · 6 个地点")).toBeVisible();
});
