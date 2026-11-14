// 文件说明：端到端发布流程测试：release-flow.spec。
import { expect, test } from "@playwright/test";

test("release candidate completes generate, edit, replan, save and share", async ({
  page,
  context,
}) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  const email = `release-flow-${Date.now()}@example.com`;

  await page.goto("/register");
  await page.getByLabel("称呼").fill("Release Candidate");
  await page.getByLabel("邮箱").fill(email);
  await page.getByLabel("密码", { exact: true }).fill("correct-horse-battery-staple");
  await page.getByLabel("确认密码").fill("correct-horse-battery-staple");
  await page.getByRole("button", { name: "创建账号" }).click();
  await expect(
    page.getByRole("heading", { name: "新的故事，从哪里开始？" }),
  ).toBeVisible();

  const token = await page.evaluate(() =>
    sessionStorage.getItem("tripmate.access-token"),
  );
  expect(token).toBeTruthy();
  const headers = { Authorization: `Bearer ${token}` };

  const created = await page.request.post(
    "http://127.0.0.1:8010/api/v1/trips",
    {
      headers,
      data: {
        brief: {
          destination: "重庆",
          origin: "上海",
          start_date: "2026-12-01",
          end_date: "2026-12-02",
          party_size: 2,
          budget_minor: 500000,
          currency: "CNY",
          interests: ["美食", "夜景"],
          pace: "balanced",
          transport_preferences: [],
          lodging_preferences: [],
          must_visit: ["洪崖洞"],
          avoid: [],
          constraints: [],
        },
      },
    },
  );
  expect(created.ok()).toBeTruthy();
  const trip = (await created.json()) as { id: string };

  const started = await page.request.post(
    `http://127.0.0.1:8010/api/v1/trips/${trip.id}/plan`,
    {
      headers,
      data: { expected_version: 1, apply_to_itinerary: true },
    },
  );
  expect(started.ok()).toBeTruthy();
  const job = (await started.json()) as { job_id: string };

  let completed = false;
  for (let attempt = 0; attempt < 80; attempt += 1) {
    const response = await page.request.get(
      `http://127.0.0.1:8010/api/v1/jobs/${job.job_id}`,
      { headers },
    );
    expect(response.ok()).toBeTruthy();
    const payload = (await response.json()) as { status: string };
    if (["completed", "partial", "failed"].includes(payload.status)) {
      expect(payload.status).not.toBe("failed");
      completed = true;
      break;
    }
    await page.waitForTimeout(250);
  }
  expect(completed).toBe(true);

  const itineraryResponse = await page.request.get(
    `http://127.0.0.1:8010/api/v1/trips/${trip.id}/itinerary`,
    { headers },
  );
  expect(itineraryResponse.ok()).toBeTruthy();
  const itinerary = (await itineraryResponse.json()) as {
    version: number;
    days: Array<{ id: string; stops: unknown[] }>;
  };
  const day = itinerary.days.find((item) => item.stops.length >= 2);
  expect(day).toBeTruthy();

  const replan = await page.request.post(
    `http://127.0.0.1:8010/api/v1/trips/${trip.id}/replan`,
    {
      headers,
      data: {
        expected_version: itinerary.version,
        day_id: day!.id,
        instruction: "减少一个景点",
      },
    },
  );
  expect(replan.ok()).toBeTruthy();
  const patch = (await replan.json()) as {
    id: string;
    base_version: number;
  };

  const applied = await page.request.post(
    `http://127.0.0.1:8010/api/v1/trips/${trip.id}/patches/${patch.id}/apply`,
    {
      headers,
      data: { expected_version: patch.base_version },
    },
  );
  expect(applied.ok()).toBeTruthy();

  await page.goto(`/trips/${trip.id}/itinerary`);
  await expect(page.getByRole("heading", { name: "逐日行程" })).toBeVisible();

  const share = await page.request.post(
    `http://127.0.0.1:8010/api/v1/trips/${trip.id}/shares`,
    {
      headers,
      data: { expires_in_days: 30 },
    },
  );
  expect(share.ok()).toBeTruthy();
  const sharePayload = (await share.json()) as { token: string };

  const publicPage = await context.newPage();
  await publicPage.goto(`/share/${sharePayload.token}`);
  await expect(publicPage.getByRole("heading", { name: "重庆" })).toBeVisible();
  await expect(publicPage.locator(".shared-itinerary")).toBeVisible();
});
