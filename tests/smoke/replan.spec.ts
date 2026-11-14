// 文件说明：Playwright 浏览器冒烟测试：replan.spec。
import { expect, test } from "@playwright/test";

test("user reviews a partial replan diff before applying a new version", async ({
  page,
}) => {
  const email = `replan-e2e-${Date.now()}@example.com`;

  await page.goto("/register");
  await page.getByLabel("称呼").fill("Replan E2E Traveler");
  await page.getByLabel("邮箱").fill(email);
  await page.getByLabel("密码", { exact: true }).fill("correct-horse-battery-staple");
  await page.getByLabel("确认密码").fill("correct-horse-battery-staple");
  await page.getByRole("button", { name: "创建账号" }).click();

  await page.getByRole("link", { name: "行程" }).first().click();
  await page.getByRole("link", { name: "新建旅行" }).first().click();
  await page.getByLabel("目的地").fill("Chongqing");
  await page.getByLabel("开始日期").fill("2026-12-01");
  await page.getByLabel("结束日期").fill("2026-12-01");
  await page.getByRole("button", { name: "创建旅行" }).click();
  await page.getByRole("link", { name: "编辑逐日行程" }).click();
  await page.getByRole("button", { name: "生成每日骨架" }).first().click();

  const day = page.getByTestId("itinerary-day").first();
  const addForm = day.getByTestId("itinerary-add-stop");
  for (const [name, time] of [
    ["Hongya Cave", "09:00"],
    ["Jiefangbei", "13:00"],
  ] as const) {
    await addForm.getByLabel("地点名称").fill(name);
    await addForm.getByLabel("开始时间").fill(time);
    await addForm.getByLabel("停留分钟").fill("60");
    await addForm.getByLabel("预计花费").fill("0");
    await addForm.getByRole("button", { name: "添加地点" }).click();
    await expect(day.getByTestId("itinerary-stop").filter({ hasText: name })).toBeVisible();
  }

  const token = await page.evaluate(() =>
    window.sessionStorage.getItem("tripmate.access-token"),
  );
  const tripId = page.url().split("/trips/")[1]?.split("/")[0];
  expect(token).toBeTruthy();
  expect(tripId).toBeTruthy();

  await page.getByRole("button", { name: "局部重排" }).click();
  await page.getByLabel("调整要求").fill("减少一个景点");
  await page.getByRole("button", { name: "生成差异" }).click();
  await expect(
    page.getByRole("heading", { name: "确认这次局部调整" }),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "将移除" })).toBeVisible();

  const beforeApply = await page.request.get(
    `http://127.0.0.1:8010/api/v1/trips/${tripId}/itinerary`,
    { headers: { Authorization: `Bearer ${token}` } },
  );
  expect(beforeApply.ok()).toBeTruthy();
  const beforeItinerary = (await beforeApply.json()) as {
    version: number;
    days: Array<{ stops: unknown[] }>;
  };
  expect(beforeItinerary.days[0]!.stops).toHaveLength(2);

  await page.getByRole("button", { name: "确认应用" }).click();
  await expect(page.getByText(/局部重排已应用/)).toBeVisible();
  await expect(day.getByTestId("itinerary-stop")).toHaveCount(1);

  const afterApply = await page.request.get(
    `http://127.0.0.1:8010/api/v1/trips/${tripId}/itinerary`,
    { headers: { Authorization: `Bearer ${token}` } },
  );
  expect(afterApply.ok()).toBeTruthy();
  const afterItinerary = (await afterApply.json()) as {
    version: number;
    days: Array<{ stops: unknown[] }>;
  };
  expect(afterItinerary.version).toBe(beforeItinerary.version + 1);
  expect(afterItinerary.days[0]!.stops).toHaveLength(1);
});
