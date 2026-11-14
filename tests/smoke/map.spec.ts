// 文件说明：Playwright 浏览器冒烟测试：map.spec。
import { expect, test, type Locator } from "@playwright/test";

test.setTimeout(60_000);

function placeResultButton(addForm: Locator, name: string): Locator {
  const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return addForm.getByRole("button", {
    name: new RegExp(`^${escaped}(?:\\s|$)`),
  });
}

test("user can calculate routes and view a real day map surface", async ({ page }) => {
  const email = `map-e2e-${Date.now()}@example.com`;
  const workers: string[] = [];
  page.on("worker", (worker) => workers.push(worker.url()));

  await page.goto("/register");
  await page.getByLabel("称呼").fill("Map E2E Traveler");
  await page.getByLabel("邮箱").fill(email);
  await page.getByLabel("密码", { exact: true }).fill("correct-horse-battery-staple");
  await page.getByLabel("确认密码").fill("correct-horse-battery-staple");
  await page.getByRole("button", { name: "创建账号" }).click();

  await page.getByRole("link", { name: "行程" }).first().click();
  await page.getByRole("link", { name: "新建旅行" }).first().click();
  await page.getByLabel("目的地").fill("Chongqing");
  await page.getByLabel("开始日期").fill("2026-12-01");
  await page.getByLabel("结束日期").fill("2026-12-02");
  await page.getByRole("button", { name: "创建旅行" }).click();
  await page.getByRole("link", { name: "编辑逐日行程" }).click();
  await page.getByRole("button", { name: "生成每日骨架" }).first().click();

  const dayTabs = page.getByTestId("itinerary-day-tab");
  await expect(dayTabs).toHaveCount(2);

  let day = page.getByTestId("itinerary-day");
  const addForm = day.getByTestId("itinerary-add-stop");
  await addForm.getByLabel("搜索地点").fill("洪崖洞");
  await addForm.getByRole("button", { name: "搜索", exact: true }).click();
  await placeResultButton(addForm, "洪崖洞民俗风貌区").click();
  await addForm.getByRole("button", { name: "添加地点" }).click();
  await expect(day.getByTestId("itinerary-stop")).toHaveCount(1);

  await addForm.getByLabel("搜索地点").fill("解放碑");
  await addForm.getByRole("button", { name: "搜索", exact: true }).click();
  await placeResultButton(addForm, "解放碑步行街").click();
  await addForm.getByRole("button", { name: "添加地点" }).click();
  await expect(day.getByTestId("itinerary-stop")).toHaveCount(2);

  await dayTabs.nth(1).click();
  const secondDay = page.getByTestId("itinerary-day");
  const secondAddForm = secondDay.getByTestId("itinerary-add-stop");
  await secondAddForm.getByLabel("搜索地点").fill("李子坝");
  await secondAddForm.getByRole("button", { name: "搜索", exact: true }).click();
  await placeResultButton(secondAddForm, "李子坝轻轨穿楼观景台").click();
  await secondAddForm.getByRole("button", { name: "添加地点" }).click();
  await expect(secondDay.getByTestId("itinerary-stop")).toHaveCount(1);

  await dayTabs.first().click();
  day = page.getByTestId("itinerary-day");
  await day.getByRole("link", { name: "地图与路线" }).click();
  await expect(page.locator(".map-route-sheet")).toBeVisible();
  await expect(page.getByRole("link", { name: "退出路书" })).toBeVisible();
  await page.getByRole("button", { name: "计算全部路线" }).click();
  const map = page.getByTestId("route-map");
  await expect(map).toBeVisible();
  await expect(map).toHaveAttribute("data-map-ready", "true");
  await expect(page.locator(".map-canvas__status")).toContainText(
    "全部行程路线已绘制",
  );
  await expect(page.locator(".map-stop-marker")).toHaveCount(2);
  await expect(page.getByText(/km|m/).first()).toBeVisible();
  await expect(page.getByText(/分钟/).first()).toBeVisible();
  await expect(page.locator(".maplibregl-ctrl-scale")).toBeVisible();
  await expect.poll(() => workers.length).toBeGreaterThan(0);
  expect(workers.some((url) => url.includes("maplibre"))).toBe(true);

  await page.getByRole("button", { name: "添加地点" }).click();
  const mapEditor = page.locator(".map-stop-editor");
  await mapEditor.getByLabel("搜索地点").fill("李子坝");
  await mapEditor.getByRole("button", { name: "搜索", exact: true }).click();
  await placeResultButton(mapEditor, "李子坝轻轨穿楼观景台").click();
  await mapEditor.getByRole("button", { name: "添加地点", exact: true }).click();
  await expect(page.getByTestId("map-stop")).toHaveCount(3);

  const transportSelects = page.getByLabel(/第 \d 段交通方式/);
  await expect(transportSelects).toHaveCount(2);
  await expect(
    transportSelects.first().locator('option[value="high_speed_rail"]'),
  ).toHaveCount(0);
  await expect(
    transportSelects.first().locator('option[value="train"]'),
  ).toHaveCount(0);
  await expect(
    transportSelects.first().locator('option[value="flight"]'),
  ).toHaveCount(1);
  expect(
    await transportSelects.first().evaluate(
      (element) => element.getBoundingClientRect().height,
    ),
  ).toBeGreaterThanOrEqual(42);
  await transportSelects.first().selectOption("bicycling");
  await expect(
    page.locator(".route-leg").first().locator(":scope > span").filter({ hasText: "骑行" }),
  ).toBeVisible();
  await transportSelects.nth(1).selectOption("subway");
  await expect(
    page.locator(".route-leg").nth(1).locator(":scope > span").filter({ hasText: "地铁" }),
  ).toBeVisible();
  await transportSelects.first().selectOption("flight");
  await expect(
    page.locator(".route-leg").first().locator(":scope > span").filter({ hasText: "飞机（示意）" }),
  ).toBeVisible();
  await expect(map).not.toHaveAttribute("data-route-features", "0");
  await page.getByRole("link", { name: "退出路书" }).click();
  await page.getByRole("link", { name: "地图与路线" }).click();
  await expect(page.getByLabel(/第 \d 段交通方式/).first()).toHaveValue("flight");
  await expect(page.getByLabel(/第 \d 段交通方式/).nth(1)).toHaveValue("subway");

  const mapStops = page.getByTestId("map-stop");
  const dataTransfer = await page.evaluateHandle(() => new DataTransfer());
  await mapStops.first().dispatchEvent("dragstart", { dataTransfer });
  await expect(mapStops.first()).toHaveClass(/is-dragging/);
  await mapStops.last().dispatchEvent("dragover", { dataTransfer });
  await mapStops.last().dispatchEvent("drop", { dataTransfer });
  await mapStops.first().dispatchEvent("dragend", { dataTransfer });
  await expect(mapStops.last()).toContainText("洪崖洞民俗风貌区");

  await page.getByRole("button", { name: "编辑 洪崖洞民俗风貌区" }).click();
  await page.locator(".map-stop-editor").getByLabel("停留分钟").fill("120");
  await page.getByRole("button", { name: "保存修改" }).click();
  await expect(page.getByText(/120 分钟/).first()).toBeVisible();

  await page.locator(".map-day-list a").nth(2).click();
  await expect(page).toHaveURL(/\/days\/.+\/map/);
  await expect(page.locator(".map-route-sheet")).toContainText("李子坝轻轨穿楼观景台");
  await expect(page.locator(".map-route-sheet")).not.toContainText("洪崖洞民俗风貌区");
});

test("route book shows every planned day and centers an empty trip on its origin", async ({
  page,
}) => {
  const email = `map-all-days-${Date.now()}@example.com`;

  await page.goto("/register");
  await page.getByLabel("称呼").fill("Map All Days E2E");
  await page.getByLabel("邮箱").fill(email);
  await page.getByLabel("密码", { exact: true }).fill("correct-horse-battery-staple");
  await page.getByLabel("确认密码").fill("correct-horse-battery-staple");
  await page.getByRole("button", { name: "创建账号" }).click();

  await page.getByRole("link", { name: "行程" }).first().click();
  await page.getByRole("link", { name: "新建旅行" }).first().click();
  await page.getByLabel("目的地").fill("Chongqing");
  await page.getByLabel("出发地").fill("Shanghai");
  await page.getByLabel("开始日期").fill("2026-12-01");
  await page.getByLabel("结束日期").fill("2026-12-02");
  await page.getByRole("button", { name: "创建旅行" }).click();
  await page.getByRole("link", { name: "编辑逐日行程" }).click();
  await page.getByRole("button", { name: "生成每日骨架" }).first().click();

  let day = page.getByTestId("itinerary-day");
  await page.getByRole("link", { name: "全程路书" }).click();
  await expect(page).toHaveURL(/\/trips\/.+\/map$/);
  await expect(page.getByTestId("route-map")).toHaveAttribute(
    "data-map-ready",
    "true",
  );
  await expect(page.locator(".map-canvas__status")).toContainText(
    "Shanghai出发地图",
  );
  await expect(page.getByTestId("route-map")).toHaveAttribute(
    "data-map-center",
    /^121\./,
  );

  await page.getByRole("link", { name: "退出路书" }).click();
  await page.getByTestId("itinerary-day-tab").nth(1).click();
  day = page.getByTestId("itinerary-day");
  const addForm = day.getByTestId("itinerary-add-stop");
  for (const [keyword, name] of [
    ["洪崖洞", "洪崖洞民俗风貌区"],
    ["解放碑", "解放碑步行街"],
  ] as const) {
    await addForm.getByLabel("搜索地点").fill(keyword);
    await addForm.getByRole("button", { name: "搜索", exact: true }).click();
    await placeResultButton(addForm, name).click();
    await addForm.getByRole("button", { name: "添加地点" }).click();
    await expect(day.getByText(name, { exact: true }).first()).toBeVisible();
  }

  await page.getByRole("link", { name: "全程路书" }).click();
  await expect(page.getByTestId("route-map")).toHaveAttribute(
    "data-map-ready",
    "true",
  );
  await expect(page.locator(".map-stop-marker")).toHaveCount(2);
  await expect(page.locator(".map-canvas__status")).toContainText(
    "全部行程路线已绘制",
  );

  await page.locator(".map-day-list a").nth(2).click();
  await expect(page).toHaveURL(/\/days\/.+\/map$/);
  await expect(page.locator(".map-stop-marker")).toHaveCount(2);

  await page.locator(".map-day-list a").nth(1).click();
  await expect(page.locator(".map-stop-marker")).toHaveCount(0);
});

test("long walking distance warns the user and flight uses a visible card arc", async ({
  page,
}) => {
  const email = `map-distance-warning-${Date.now()}@example.com`;

  await page.goto("/register");
  await page.getByLabel("称呼").fill("Map Distance E2E");
  await page.getByLabel("邮箱").fill(email);
  await page.getByLabel("密码", { exact: true }).fill("correct-horse-battery-staple");
  await page.getByLabel("确认密码").fill("correct-horse-battery-staple");
  await page.getByRole("button", { name: "创建账号" }).click();

  await page.getByRole("link", { name: "行程" }).first().click();
  await page.getByRole("link", { name: "新建旅行" }).first().click();
  await page.getByLabel("目的地").fill("新疆");
  await page.getByLabel("出发地").fill("上海");
  await page.getByLabel("开始日期").fill("2026-12-01");
  await page.getByLabel("结束日期").fill("2026-12-01");
  await page.getByRole("button", { name: "创建旅行" }).click();
  await page.getByRole("link", { name: "编辑逐日行程" }).click();
  await page.getByRole("button", { name: "生成每日骨架" }).first().click();

  const day = page.getByTestId("itinerary-day");
  const addForm = day.getByTestId("itinerary-add-stop");
  await addForm.getByText("坐标与来源（可选）").click();
  for (const [name, time, longitude, latitude] of [
    ["上海外滩", "08:00", "121.4905", "31.2417"],
    ["赛里木湖", "14:00", "81.2036", "44.6031"],
  ] as const) {
    await addForm.getByLabel("地点名称").fill(name);
    await addForm.getByLabel("开始时间").fill(time);
    await addForm.getByLabel("停留分钟").fill("60");
    await addForm.getByLabel("预计花费").fill("0");
    await addForm.getByLabel("经度").fill(longitude);
    await addForm.getByLabel("纬度").fill(latitude);
    await addForm.getByRole("button", { name: "添加地点" }).click();
    await expect(day.getByText(name, { exact: true }).first()).toBeVisible();
  }

  await day.getByRole("link", { name: "地图与路线" }).click();
  const mode = page.getByLabel("第 1 段交通方式");
  await mode.selectOption("driving");
  await mode.selectOption("walking");
  const warning = page.getByRole("dialog", { name: "步行距离过长" });
  await expect(warning).toBeVisible();
  await expect(warning).toContainText("建议改为驾车、公交、地铁或飞机");
  await warning.getByRole("button", { name: "改为驾车" }).click();
  await expect(mode).toHaveValue("driving");

  await mode.selectOption("flight");
  await expect(
    page.locator(".route-leg").locator(":scope > span").filter({
      hasText: "飞机（示意）",
    }),
  ).toBeVisible();
  await expect(page.getByTestId("route-map")).not.toHaveAttribute(
    "data-route-features",
    "0",
  );
  const cardStyle = await page
    .locator(".map-route-sheet .route-stop")
    .first()
    .evaluate((element) => {
      const style = getComputedStyle(element);
      return {
        borderWidth: style.borderTopWidth,
        shadow: style.boxShadow,
      };
    });
  expect(cardStyle.borderWidth).not.toBe("0px");
  expect(cardStyle.shadow).not.toBe("none");
});
