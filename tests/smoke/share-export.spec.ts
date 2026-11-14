// 文件说明：Playwright 浏览器冒烟测试：share-export.spec。
import { expect, test } from "@playwright/test";

test("user can favorite places, share a read-only itinerary and export it", async ({
  page,
  context,
}) => {
  const email = `share-e2e-${Date.now()}@example.com`;
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);

  await page.goto("/register");
  await page.getByLabel("称呼").fill("Share E2E Traveler");
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
  await expect(page.getByRole("heading", { name: "Chongqing" })).toBeVisible();

  const token = await page.evaluate(() =>
    window.sessionStorage.getItem("tripmate.access-token"),
  );
  const tripId = page.url().split("/trips/")[1]?.split(/[/?]/)[0];
  expect(token).toBeTruthy();
  expect(tripId).toBeTruthy();
  const dayResponse = await page.request.post(
    `http://127.0.0.1:8010/api/v1/trips/${tripId}/days`,
    {
      headers: { Authorization: `Bearer ${token}` },
      data: { expected_version: 1, date: "2026-12-01" },
    },
  );
  expect(dayResponse.ok()).toBeTruthy();
  const day = (await dayResponse.json()) as { id: string };
  const stopResponse = await page.request.post(
    `http://127.0.0.1:8010/api/v1/days/${day.id}/stops`,
    {
      headers: { Authorization: `Bearer ${token}` },
      data: {
        expected_version: 2,
        place_id: "mock-hongyadong",
        place_name: "洪崖洞民俗风貌区",
        start_at: "2026-12-01T09:00:00",
        duration_minutes: 90,
        estimated_cost_minor: 5000,
      },
    },
  );
  expect(stopResponse.ok()).toBeTruthy();
  await page.reload();

  await page.getByRole("button", { name: "分享与导出" }).click();
  const createResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      response.url().endsWith(`/api/v1/trips/${tripId}/shares`),
  );
  await page.getByRole("button", { name: "创建分享链接" }).click();
  const sharePayload = (await (await createResponse).json()) as {
    token: string;
    url_path: string;
  };
  await expect(page.getByText("分享链接已复制")).toBeVisible();

  const publicPage = await context.newPage();
  await publicPage.goto(`/share/${sharePayload.token}`);
  await expect(publicPage.getByRole("heading", { name: "Chongqing" })).toBeVisible();
  await expect(publicPage.getByText("洪崖洞民俗风貌区")).toBeVisible();
  await expect(publicPage.getByText("版本 v3", { exact: true })).toBeVisible();
  const publicText = await publicPage.locator("body").innerText();
  expect(publicText).not.toContain("owner_id");
  expect(publicText).not.toContain("budget_minor");

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "导出图片" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/\.png$/);

  await page.getByRole("button", { name: "撤销分享链接" }).click();
  await expect(page.getByText("分享已撤销")).toBeVisible();
  await publicPage.reload();
  await expect(publicPage.getByText("无法打开这份路书")).toBeVisible();

  await page.goto("/places");
  await page.getByLabel("搜索地点").fill("洪崖洞");
  await page.getByRole("button", { name: "搜索", exact: true }).click();
  const favoriteButton = page.getByRole("button", {
    name: "收藏 洪崖洞民俗风貌区",
  });
  await favoriteButton.click();
  await expect(
    page.getByRole("button", { name: "取消收藏 洪崖洞民俗风貌区" }),
  ).toBeVisible();
});
