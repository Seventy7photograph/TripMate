// 文件说明：Playwright 端到端测试配置。
import { defineConfig, devices } from "@playwright/test";
import { env } from "node:process";

const webPort = env.E2E_WEB_PORT ?? "5173";
const adminPort = env.E2E_ADMIN_PORT ?? "5174";
const webUrl = `http://127.0.0.1:${webPort}`;
const adminUrl = `http://127.0.0.1:${adminPort}`;

export default defineConfig({
  testDir: "./tests",
  fullyParallel: true,
  workers: 1,
  forbidOnly: Boolean(env.CI),
  retries: env.CI ? 2 : 0,
  reporter: "list",
  expect: {
    timeout: 10_000,
  },
  timeout: 45_000,
  use: {
    baseURL: webUrl,
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: [
    {
      command:
        "node scripts/uv.mjs run --project apps/api python apps/api/run.py --host 127.0.0.1 --port 8010",
      url: "http://127.0.0.1:8010/api/v1/health",
      reuseExistingServer: !env.CI,
      timeout: 120_000,
      env: {
        APP_ENV: "test",
        MODEL_CONFIG_DB_ENABLED: "false",
        PROVIDER_PROFILE: "mock",
        MAP_PROVIDER_PROFILE: "mock",
      },
    },
    {
      command:
        `corepack pnpm --filter @tripmate/web dev --host 127.0.0.1 --port ${webPort}`,
      url: webUrl,
      reuseExistingServer: !env.CI,
      timeout: 120_000,
      env: {
        VITE_API_PROXY_TARGET: "http://127.0.0.1:8010",
      },
    },
    {
      command:
        `corepack pnpm --filter @tripmate/admin dev --host 127.0.0.1 --port ${adminPort}`,
      url: adminUrl,
      reuseExistingServer: !env.CI,
      timeout: 120_000,
      env: {
        VITE_API_PROXY_TARGET: "http://127.0.0.1:8010",
      },
    },
  ],
});
