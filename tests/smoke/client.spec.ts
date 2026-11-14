// 文件说明：Playwright 浏览器冒烟测试：client.spec。
import { expect, test } from "@playwright/test";

test("user can register, survive refresh and edit profile", async ({ page }) => {
  const email = `e2e-${Date.now()}@example.com`;

  await page.goto("/register");
  await page.getByLabel("称呼").fill("E2E Traveler");
  await page.getByLabel("邮箱").fill(email);
  await page.getByLabel("密码", { exact: true }).fill("correct-horse-battery-staple");
  await page.getByLabel("确认密码").fill("correct-horse-battery-staple");
  await page.getByRole("button", { name: "创建账号" }).click();

  await expect(
    page.getByRole("heading", { name: "新的故事，从哪里开始？" }),
  ).toBeVisible();
  await expect(page.locator(".app-profile-link")).toBeVisible();

  await page.reload();
  await expect(
    page.getByRole("heading", { name: "新的故事，从哪里开始？" }),
  ).toBeVisible();

  await page.locator(".app-profile-link").click();
  await expect(page.getByRole("heading", { name: "个人资料" })).toBeVisible();

  await page.getByLabel("默认出发地").fill("Shanghai");
  await page.getByRole("button", { name: "保存资料" }).click();
  await expect(page.getByText("个人资料已保存")).toBeVisible();

  await page.getByRole("button", { name: "退出登录" }).click();
  await expect(page.getByRole("dialog", { name: "退出当前账号？" })).toBeVisible();
  await page.getByRole("button", { name: "继续使用" }).click();
  await expect(page.getByRole("heading", { name: "个人资料" })).toBeVisible();

  await page.getByRole("button", { name: "退出登录" }).click();
  await page.getByRole("button", { name: "确认退出" }).click();
  await expect(page).toHaveURL(/\/login/);
});

test("auth errors clear when switching modes and validate fields inline", async ({
  page,
}) => {
  await page.goto("/login");
  await page.getByLabel("邮箱").fill("missing@example.com");
  await page.getByLabel("密码", { exact: true }).fill("wrong-password");
  await page.getByRole("button", { name: "出发" }).click();
  await expect(page.getByText("邮箱或密码不正确")).toBeVisible();
  await expect(page.getByText("登录后开始新的对话")).toHaveCount(0);

  await page.getByRole("link", { name: "创建账号" }).click();
  await expect(page).toHaveURL(/\/register/);
  await expect(page.getByText("邮箱或密码不正确")).toHaveCount(0);

  await page.getByLabel("邮箱").fill("not-an-email");
  await page.getByLabel("密码", { exact: true }).fill("short");
  await page.getByLabel("确认密码").fill("different");
  await page.getByRole("button", { name: "创建账号" }).click();
  await expect(page.getByText("请输入有效邮箱")).toBeVisible();
  await expect(page.getByText("密码至少 12 位")).toBeVisible();
  await expect(page.getByText("两次输入的密码不一致")).toBeVisible();
});

test("primary navigation stays stable and the shortcut is not displayed", async ({
  page,
}) => {
  const email = `navigation-e2e-${Date.now()}@example.com`;

  await page.goto("/register");
  await page.getByLabel("称呼").fill("Navigation E2E");
  await page.getByLabel("邮箱").fill(email);
  await page.getByLabel("密码", { exact: true }).fill("correct-horse-battery-staple");
  await page.getByLabel("确认密码").fill("correct-horse-battery-staple");
  await page.getByRole("button", { name: "创建账号" }).click();

  await expect(page.getByText(/Ctrl\+Enter/i)).toHaveCount(0);
  const initialBar = await page.locator(".app-topbar").boundingBox();
  expect(initialBar).not.toBeNull();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(
    await page.evaluate(() => window.innerWidth),
  );

  await page.getByRole("link", { name: "行程" }).first().click();
  await expect(page.getByRole("heading", { name: "旅行计划" })).toBeVisible();
  const tripsBar = await page.locator(".app-topbar").boundingBox();
  expect(tripsBar).toEqual(initialBar);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(
    await page.evaluate(() => window.innerWidth),
  );

  await page.getByRole("link", { name: "探索" }).first().click();
  await expect(page.getByRole("heading", { name: "目的地与地点" })).toBeVisible();
  const placesBar = await page.locator(".app-topbar").boundingBox();
  expect(placesBar).toEqual(initialBar);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(
    await page.evaluate(() => window.innerWidth),
  );
});

test("Enter sends the message and Shift+Enter inserts a newline", async ({ page }) => {
  const email = `composer-keyboard-${Date.now()}@example.com`;

  await page.route("**/api/v1/chat/respond", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        intent: "clarify",
        in_scope: true,
        confidence: 0.9,
        answer: null,
        sources: [],
        selected_skills: [],
        used_tools: [],
        requires_planning: false,
        brief: null,
        draft: { destination: "泉州" },
        missing_fields: ["start_date"],
        questions: ["请提供具体日期。"],
        model_name: "mock-tripbrief-v1",
      }),
    });
  });

  await page.goto("/register");
  await page.getByLabel("称呼").fill("Composer Keyboard E2E");
  await page.getByLabel("邮箱").fill(email);
  await page.getByLabel("密码", { exact: true }).fill("correct-horse-battery-staple");
  await page.getByLabel("确认密码").fill("correct-horse-battery-staple");
  await page.getByRole("button", { name: "创建账号" }).click();

  const composer = page.getByLabel("旅行问题或需求");
  await composer.fill("第一行");
  await composer.press("Shift+Enter");
  await expect(composer).toHaveValue("第一行\n");

  await composer.fill("2026年12月1日去泉州");
  await composer.press("Enter");
  await expect(page.getByText("请提供具体日期。")).toBeVisible();
});
