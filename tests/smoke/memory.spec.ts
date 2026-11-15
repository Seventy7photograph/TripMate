// 文件说明：Playwright 浏览器冒烟测试：memory.spec。
import { expect, test } from "@playwright/test";

test("user controls authorized travel memories", async ({ page }) => {
  const email = `memory-e2e-${Date.now()}@example.com`;

  await page.goto("/register");
  await page.getByLabel("称呼").fill("Memory E2E Traveler");
  await page.getByLabel("邮箱").fill(email);
  await page.getByLabel("密码", { exact: true }).fill("correct-horse-battery-staple");
  await page.getByLabel("确认密码").fill("correct-horse-battery-staple");
  await page.getByRole("button", { name: "创建账号" }).click();

  await page.locator(".app-profile-link").click();
  await page.getByRole("link", { name: "旅行记忆" }).click();
  await expect(page.getByRole("heading", { name: "旅行记忆" })).toBeVisible();

  await page
    .getByPlaceholder("例如：住宿优先靠近地铁站")
    .fill("住宿优先靠近地铁站");
  await page.getByLabel("允许用于后续规划").check();
  await page.getByRole("button", { name: "保存记忆" }).click();
  await expect(page.getByText("住宿优先靠近地铁站")).toBeVisible();

  await page.getByRole("button", { name: "停用记忆" }).click();
  await expect(page.getByRole("button", { name: "启用记忆" })).toBeVisible();

  await page.getByRole("button", { name: "删除记忆" }).click();
  await expect(page.getByRole("dialog", { name: "删除这条记忆？" })).toBeVisible();
  await page.getByRole("button", { name: "确认删除" }).click();
  await expect(page.getByText("还没有旅行记忆")).toBeVisible();
});

test("a new login starts a blank conversation and history stays manual", async ({
  page,
}) => {
  const email = `login-history-e2e-${Date.now()}@example.com`;
  const password = "correct-horse-battery-staple";

  await page.goto("/register");
  await page.getByLabel("称呼").fill("Login History Traveler");
  await page.getByLabel("邮箱").fill(email);
  await page.getByLabel("密码", { exact: true }).fill(password);
  await page.getByLabel("确认密码").fill(password);
  await page.getByRole("button", { name: "创建账号" }).click();

  await page
    .getByLabel("旅行问题或需求")
    .fill("2026年12月1日到12月3日，2个人从上海去重庆，喜欢美食。");
  await page.getByRole("button", { name: "开始规划" }).click();
  await expect(page.getByText("已生成")).toBeVisible({ timeout: 15_000 });

  await page.locator(".app-profile-link").click();
  await page.getByRole("button", { name: "退出登录" }).click();
  await page.getByRole("button", { name: "确认退出" }).click();
  await expect(page).toHaveURL(/\/login/);

  await page.getByLabel("邮箱").fill(email);
  await page.getByLabel("密码", { exact: true }).fill(password);
  await page.getByRole("button", { name: "出发" }).click();

  await expect(
    page.getByRole("heading", { name: "新的故事，从哪里开始？" }),
  ).toBeVisible();
  await expect(page.getByText("这次旅行的总预算大约是多少？")).toHaveCount(0);

  await page.getByRole("link", { name: "行程" }).first().click();
  await page.getByRole("link", { name: "对话" }).first().click();
  await expect(
    page.getByRole("heading", { name: "新的故事，从哪里开始？" }),
  ).toBeVisible();
  await expect(page.getByText("这次旅行的总预算大约是多少？")).toHaveCount(0);

  await page.getByRole("button", { name: "历史对话" }).click();
  await expect(page.getByRole("region", { name: "历史对话" })).toBeVisible();
  await expect(page.getByText("重庆").first()).toBeVisible();
});
