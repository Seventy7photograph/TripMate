// 文件说明：Playwright 浏览器冒烟测试：admin.spec。
import { execFileSync } from "node:child_process";
import { join } from "node:path";
import { expect, test } from "@playwright/test";

test.setTimeout(90_000);
const adminUrl =
  process.env.E2E_ADMIN_URL ?? "http://127.0.0.1:5174";

test("admin can inspect operations and toggle a provider", async ({
  page,
  request,
}) => {
  const email = `admin-e2e-${Date.now()}@example.com`;
  const password = "correct-horse-battery-staple";

  const registration = await request.post(
    "http://127.0.0.1:8010/api/v1/auth/register",
    {
      data: {
        email,
        password,
        display_name: "Admin E2E",
      },
    },
  );
  expect(registration.ok()).toBeTruthy();

  execFileSync(
    process.execPath,
    [
      "../../scripts/uv.mjs",
      "run",
      "--project",
      ".",
      "python",
      "-m",
      "app.cli.promote_admin",
      email,
    ],
    {
      cwd: join(process.cwd(), "apps/api"),
      env: process.env,
      stdio: "pipe",
      timeout: 120_000,
    },
  );

  await page.goto(adminUrl);
  await page.getByLabel("邮箱").fill(email);
  await page.getByLabel("密码").fill(password);
  await page.getByRole("button", { name: "进入后台" }).click();

  await expect(page.getByRole("heading", { name: "运行概览" })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "管理后台导航" })).toBeVisible();

  const briefFeature = page.locator(".feature-list article").filter({
    hasText: "旅行需求解析",
  });
  await briefFeature.getByRole("switch", { name: "停用旅行需求解析" }).click();
  await expect(
    briefFeature.getByRole("switch", { name: "启用旅行需求解析" }),
  ).toBeVisible();
  await briefFeature.getByRole("switch", { name: "启用旅行需求解析" }).click();
  await expect(
    briefFeature.getByRole("switch", { name: "停用旅行需求解析" }),
  ).toBeVisible();

  await page.getByRole("button", { name: "Provider" }).click();
  await expect(page.getByRole("heading", { name: "Provider" })).toBeVisible();
  const mapProvider = page.locator(".provider-card").filter({
    hasText: "地图 Provider",
  });
  await mapProvider.getByRole("button", { name: "停用 Provider" }).click();
  await expect(
    mapProvider.getByRole("button", { name: "启用 Provider" }),
  ).toBeVisible();
  await mapProvider.getByRole("button", { name: "启用 Provider" }).click();
  await expect(
    mapProvider.getByRole("button", { name: "停用 Provider" }),
  ).toBeVisible();

  await page.getByRole("button", { name: "Agent Runs" }).click();
  await expect(page.getByRole("heading", { name: "Agent Runs" })).toBeVisible();
  await expect(page.locator(".admin-table")).toBeVisible();

  await page.getByRole("button", { name: "模型配置" }).click();
  await expect(page.getByRole("heading", { name: "模型配置" })).toBeVisible();
  const briefConfig = page.locator(".model-card").filter({
    hasText: "旅行需求解析",
  });
  await expect(briefConfig.getByRole("button", { name: "Mock" })).toHaveCount(0);
  await expect(briefConfig.getByText("Live", { exact: true })).toBeVisible();
  await briefConfig.getByPlaceholder("deepseek-flash").fill("deepseek-flash");
  await briefConfig.getByRole("button", { name: "保存配置" }).click();
  await expect(
    page.getByText("旅行需求解析配置已保存"),
  ).toBeVisible();
  await expect(briefConfig.getByText("在线配置")).toBeVisible();

  await page.getByRole("button", { name: "成本" }).click();
  await expect(page.getByRole("heading", { name: "成本" })).toBeVisible();
  await expect(page.locator(".limit-strip")).toBeVisible();

  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator(".admin-nav")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(390);
});
