// 文件说明：Playwright 浏览器冒烟测试：versions.spec。
import { expect, test, type Page } from "@playwright/test";

async function createTripWithStop(page: Page): Promise<void> {
  const email = `versions-e2e-${Date.now()}-${Math.random()}@example.com`;

  await page.goto("/register");
  await page.getByLabel("称呼").fill("Version E2E Traveler");
  await page.getByLabel("邮箱").fill(email);
  await page.getByLabel("密码", { exact: true }).fill("correct-horse-battery-staple");
  await page.getByLabel("确认密码").fill("correct-horse-battery-staple");
  await page.getByRole("button", { name: "创建账号" }).click();

  await page.getByRole("link", { name: "行程" }).first().click();
  await page.getByRole("link", { name: "新建旅行" }).first().click();
  await page.getByLabel("目的地").fill("Chongqing");
  await page.getByLabel("出发地").fill("Shanghai");
  await page.getByLabel("开始日期").fill("2026-12-01");
  await page.getByLabel("结束日期").fill("2026-12-01");
  await page.getByLabel("出行人数").fill("2");
  await page.getByRole("button", { name: "创建旅行" }).click();

  await page.getByRole("link", { name: "编辑逐日行程" }).click();
  await page.getByRole("button", { name: "生成每日骨架" }).first().click();

  const day = page.getByTestId("itinerary-day").first();
  const addForm = day.getByTestId("itinerary-add-stop");
  await addForm.getByLabel("地点名称").fill("Hongya Cave");
  await addForm.getByLabel("开始时间").fill("09:00");
  await addForm.getByLabel("停留分钟").fill("60");
  await addForm.getByLabel("预计花费").fill("0");
  await addForm.getByRole("button", { name: "添加地点" }).click();
  await expect(day.getByTestId("itinerary-stop")).toContainText("Hongya Cave");
}

async function currentItinerary(page: Page) {
  const token = await page.evaluate(() =>
    window.sessionStorage.getItem("tripmate.access-token"),
  );
  const tripId = page.url().split("/trips/")[1]?.split("/")[0];
  expect(token).toBeTruthy();
  expect(tripId).toBeTruthy();
  const response = await page.request.get(
    `http://127.0.0.1:8010/api/v1/trips/${tripId}/itinerary`,
    {
      headers: { Authorization: `Bearer ${token}` },
    },
  );
  expect(response.ok()).toBeTruthy();
  return {
    token: token!,
    tripId: tripId!,
    itinerary: (await response.json()) as {
      version: number;
      days: Array<{ stops: Array<{ id: string; start_at: string }> }>;
    },
  };
}

test("autosave keeps a local draft when the network save fails", async ({ page }) => {
  await createTripWithStop(page);
  const stop = page.getByTestId("itinerary-stop").first();
  let failedOnce = false;

  await page.route("**/api/v1/stops/*", async (route) => {
    if (route.request().method() === "PATCH" && !failedOnce) {
      failedOnce = true;
      await route.abort("internetdisconnected");
      return;
    }
    await route.continue();
  });

  await stop.getByLabel("开始时间").fill("10:00");
  await expect(page.getByText("保存失败，草稿已保留")).toBeVisible();
  const draftKey = await page.evaluate(() =>
    Object.keys(window.localStorage).find((key) =>
      key.startsWith("tripmate.itinerary.stop-draft."),
    ),
  );
  expect(draftKey).toBeTruthy();

  await page.unroute("**/api/v1/stops/*");
  await page.reload();

  const reloadedStop = page.getByTestId("itinerary-stop").first();
  await expect(reloadedStop.getByLabel("开始时间")).toHaveValue("10:00");
  await expect(reloadedStop.getByText("已自动保存")).toBeVisible();
});

test("version conflict supports copying, loading server and keeping local", async ({
  page,
}) => {
  await createTripWithStop(page);

  let current = await currentItinerary(page);
  const stopId = current.itinerary.days[0]!.stops[0]!.id;
  const serverBump = await page.request.patch(
    `http://127.0.0.1:8010/api/v1/stops/${stopId}`,
    {
      headers: { Authorization: `Bearer ${current.token}` },
      data: {
        expected_version: current.itinerary.version,
        duration_minutes: 75,
      },
    },
  );
  expect(serverBump.ok()).toBeTruthy();

  let stop = page.getByTestId("itinerary-stop").first();
  await stop.getByLabel("开始时间").fill("10:30");
  await expect(
    page.getByRole("heading", { name: "这份旅行已在别处更新" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "复制差异" }).click();
  await expect(page.getByRole("button", { name: "已复制" })).toBeVisible();

  await page.getByRole("button", { name: "载入服务端" }).click();
  await expect(page).toHaveURL(/\/trips\/.+\/itinerary/);
  stop = page.getByTestId("itinerary-stop").first();
  await expect(stop.getByLabel("开始时间")).toHaveValue("09:00");

  current = await currentItinerary(page);
  const secondBump = await page.request.patch(
    `http://127.0.0.1:8010/api/v1/stops/${stopId}`,
    {
      headers: { Authorization: `Bearer ${current.token}` },
      data: {
        expected_version: current.itinerary.version,
        duration_minutes: 90,
      },
    },
  );
  expect(secondBump.ok()).toBeTruthy();

  await stop.getByLabel("开始时间").fill("11:00");
  await expect(
    page.getByRole("heading", { name: "这份旅行已在别处更新" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "保留本地" }).click();
  await expect(
    page.getByRole("heading", { name: "这份旅行已在别处更新" }),
  ).toHaveCount(0);
  await expect(page.getByText("已保留本地改动并生成新版本")).toBeVisible();
  await expect(stop.getByLabel("开始时间")).toHaveValue("11:00");

  await page.getByRole("button", { name: "版本历史" }).click();
  await expect(page.getByRole("heading", { name: "版本历史" })).toBeVisible();
  await expect(page.getByText("当前", { exact: true })).toBeVisible();
});
