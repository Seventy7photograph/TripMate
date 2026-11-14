// 文件说明：端到端发布流程测试：Agent Skill 灰度、审计与回退入口。

import { execFileSync } from "node:child_process";
import { join } from "node:path";
import { expect, test } from "@playwright/test";

test.setTimeout(120_000);
const adminUrl =
  process.env.E2E_ADMIN_URL ?? "http://127.0.0.1:5174";

test("admin can inspect and roll back agent skills", async ({
  page,
  request,
}) => {
  const email = `agent-skill-e2e-${Date.now()}@example.com`;
  const password = "correct-horse-battery-staple";
  const registration = await request.post(
    "http://127.0.0.1:8010/api/v1/auth/register",
    {
      data: {
        email,
        password,
        display_name: "Agent Skill E2E",
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

  const skillsFeature = page.locator(".feature-list article").filter({
    hasText: "Agent Skills",
  });
  await skillsFeature.getByRole("switch", { name: "停用Agent Skills" }).click();
  await expect(
    skillsFeature.getByRole("switch", { name: "启用Agent Skills" }),
  ).toBeVisible();
  await skillsFeature.getByRole("switch", { name: "启用Agent Skills" }).click();
  await expect(
    skillsFeature.getByRole("switch", { name: "停用Agent Skills" }),
  ).toBeVisible();

  await page.getByRole("button", { name: "Skills" }).click();
  await expect(page.getByRole("heading", { name: "Agent Skills" })).toBeVisible();
  const research = page.locator(".skill-card").filter({
    hasText: "destination-research",
  });
  await expect(research.getByText("1.0.0")).toBeVisible();
  await expect(research.getByText("search_places")).toBeVisible();
  await research.getByRole("switch", { name: "停用 Skill" }).click();
  await expect(
    research.getByRole("switch", { name: "启用 Skill" }),
  ).toBeVisible();
  await research.getByRole("switch", { name: "启用 Skill" }).click();
  await expect(
    research.getByRole("switch", { name: "停用 Skill" }),
  ).toBeVisible();

  await page.getByRole("button", { name: "Agent Runs" }).click();
  await expect(page.getByRole("heading", { name: "Agent Runs" })).toBeVisible();
  await expect(page.getByText("Skill / Router")).toBeVisible();

  await page.getByRole("button", { name: "Provider" }).click();
  await expect(page.getByText("MCP Connectors")).toBeVisible();
  await expect(page.getByText("Local Tool Health")).toBeVisible();

  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(390);
});
