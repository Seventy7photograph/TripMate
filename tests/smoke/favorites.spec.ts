// 文件说明：Playwright 浏览器冒烟测试：favorites.spec。
import { expect, test } from "@playwright/test";

test("user can organize favorites into folders with notes", async ({ page }) => {
  const email = `favorites-e2e-${Date.now()}@example.com`;

  await page.goto("/register");
  await page.getByLabel("称呼").fill("Favorites Traveler");
  await page.getByLabel("邮箱").fill(email);
  await page.getByLabel("密码", { exact: true }).fill("correct-horse-battery-staple");
  await page.getByLabel("确认密码").fill("correct-horse-battery-staple");
  await page.getByRole("button", { name: "创建账号" }).click();

  await page.getByRole("link", { name: "探索" }).first().click();
  await page.getByLabel("搜索地点").fill("洪崖洞");
  await page.getByRole("button", { name: "搜索", exact: true }).click();
  await page.getByRole("button", { name: "收藏 洪崖洞民俗风貌区" }).click();
  await expect(
    page.getByRole("button", { name: "取消收藏 洪崖洞民俗风貌区" }),
  ).toBeVisible();
  const activeFavorite = page.getByRole("button", {
    name: "取消收藏 洪崖洞民俗风貌区",
  });
  await expect(activeFavorite).toHaveClass(/is-favorite/);
  await expect(activeFavorite.locator("svg")).toHaveAttribute(
    "fill",
    "currentColor",
  );

  await page.getByRole("link", { name: "收藏" }).first().click();
  await expect(page.getByRole("heading", { name: "收藏" })).toBeVisible();
  await expect(page.getByRole("tab", { name: /全部收藏/ })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(page.getByText("洪崖洞民俗风貌区")).toBeVisible();
  await expect(page.getByText(/地点收藏/).first()).toBeVisible();
  expect(
    await page.getByLabel("收藏夹").evaluate(
      (element) => element.getBoundingClientRect().height,
    ),
  ).toBeGreaterThanOrEqual(42);

  await page.getByRole("button", { name: "编辑收藏 洪崖洞民俗风貌区" }).click();
  const dialog = page.getByRole("dialog", { name: "洪崖洞民俗风貌区" });
  await dialog.getByLabel("收藏夹").fill("重庆夜景");
  await dialog.getByLabel("备注").fill("下次带相机");
  await dialog.getByRole("button", { name: "保存" }).click();
  const favoriteRow = page.locator(".favorite-row").filter({
    hasText: "洪崖洞民俗风貌区",
  });
  await expect(favoriteRow).toContainText("重庆夜景");
  await expect(favoriteRow).toContainText("下次带相机");

  page.on("dialog", (confirmation) => confirmation.accept());
  await page.getByRole("button", { name: "删除收藏 洪崖洞民俗风貌区" }).click();
  await expect(page.getByText("还没有收藏")).toBeVisible();
});
