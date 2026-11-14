// 文件说明：Playwright 浏览器冒烟测试：itinerary.spec。
import { expect, test } from "@playwright/test";

test("user can build, edit, reorder and delete a multi-day itinerary", async ({ page }) => {
  const email = `itinerary-e2e-${Date.now()}@example.com`;

  await page.goto("/register");
  await page.getByLabel("称呼").fill("Itinerary E2E Traveler");
  await page.getByLabel("邮箱").fill(email);
  await page.getByLabel("密码", { exact: true }).fill("correct-horse-battery-staple");
  await page.getByLabel("确认密码").fill("correct-horse-battery-staple");
  await page.getByRole("button", { name: "创建账号" }).click();

  await page.getByRole("link", { name: "行程" }).first().click();
  await page.getByRole("link", { name: "新建旅行" }).first().click();
  await page.getByLabel("目的地").fill("Chongqing");
  await page.getByLabel("出发地").fill("Shanghai");
  await page.getByLabel("开始日期").fill("2026-12-01");
  await page.getByLabel("结束日期").fill("2026-12-03");
  await page.getByLabel("出行人数").fill("2");
  await page.getByRole("button", { name: "创建旅行" }).click();

  await page.getByRole("link", { name: "编辑逐日行程" }).click();
  await expect(
    page.getByRole("heading", { name: "逐日行程", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "生成每日骨架" }).first().click();
  await expect(page.getByTestId("itinerary-day-tab")).toHaveCount(3);
  await expect(page.getByTestId("itinerary-day")).toHaveCount(1);

  const dayOne = page.getByTestId("itinerary-day").first();
  await expect(dayOne.getByText("第 1 天")).toBeVisible();
  await expect(dayOne.getByText("2026年12月1日")).toBeVisible();

  const addStopForm = dayOne.getByTestId("itinerary-add-stop");
  await addStopForm.getByLabel("搜索地点").fill("洪崖洞");
  await addStopForm.getByRole("button", { name: "搜索", exact: true }).click();
  await addStopForm.getByRole("button", { name: /洪崖洞民俗风貌区/ }).click();
  await expect(addStopForm.getByLabel("地点名称")).toHaveValue("洪崖洞民俗风貌区");
  await addStopForm.getByLabel("开始时间").fill("09:00");
  await addStopForm.getByLabel("停留分钟").fill("120");
  await addStopForm.getByLabel("预计花费").fill("0");
  await addStopForm.getByRole("button", { name: "添加地点" }).click();
  await expect(
    dayOne
      .getByTestId("itinerary-stop")
      .filter({ hasText: "洪崖洞民俗风貌区" }),
  ).toBeVisible();

  await addStopForm.getByLabel("地点名称").fill("Jiefangbei");
  await addStopForm.getByLabel("开始时间").fill("13:00");
  await addStopForm.getByLabel("停留分钟").fill("60");
  await addStopForm.getByLabel("预计花费").fill("32.5");
  await addStopForm.getByRole("button", { name: "添加地点" }).click();
  await expect(
    dayOne.getByTestId("itinerary-stop").filter({ hasText: "Jiefangbei" }),
  ).toBeVisible();

  await dayOne.getByRole("button", { name: "上移 Jiefangbei" }).click();
  const stopRows = dayOne.getByTestId("itinerary-stop");
  await expect(stopRows.nth(0)).toContainText("Jiefangbei");
  await expect(stopRows.nth(1)).toContainText("洪崖洞民俗风貌区");

  const jiefangbei = stopRows.filter({ hasText: "Jiefangbei" });
  await jiefangbei.getByLabel("开始时间").fill("14:30");
  await jiefangbei.getByRole("button", { name: "保存 Jiefangbei" }).click();
  await expect(dayOne.getByText("Jiefangbei 已保存")).toBeVisible();

  await page.reload();
  await expect(page.getByTestId("itinerary-stop").first()).toContainText("Jiefangbei");

  const hongya = page
    .getByTestId("itinerary-stop")
    .filter({ hasText: "洪崖洞民俗风貌区" });
  page.on("dialog", (dialog) => dialog.accept());
  await hongya.getByRole("button", { name: "删除 洪崖洞民俗风貌区" }).click();
  await expect(
    page
      .getByTestId("itinerary-stop")
      .filter({ hasText: "洪崖洞民俗风貌区" }),
  ).toHaveCount(0);
});
