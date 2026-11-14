// 文件说明：Playwright 浏览器冒烟测试：multimodal.spec。
import { expect, test } from "@playwright/test";

const ONE_PIXEL_PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAEklEQVR4nGOUi+phYGBgYgADAAvsAQj5DFdqAAAAAElFTkSuQmCC",
  "base64",
);

test("user can attach a document and image to the planning conversation", async ({
  page,
}) => {
  const email = `multimodal-e2e-${Date.now()}@example.com`;
  await page.goto("/register");
  await page.getByLabel("称呼").fill("Multimodal Traveler");
  await page.getByLabel("邮箱").fill(email);
  await page.getByLabel("密码", { exact: true }).fill("correct-horse-battery-staple");
  await page.getByLabel("确认密码").fill("correct-horse-battery-staple");
  await page.getByRole("button", { name: "创建账号" }).click();

  await page.locator('input[type="file"]').first().setInputFiles([
    {
      name: "trip-notes.txt",
      mimeType: "text/plain",
      buffer: Buffer.from(
        "2026年12月1日到12月3日，2个人从上海去重庆，预算5000元，喜欢美食和夜景。",
      ),
    },
    {
      name: "hotel-view.png",
      mimeType: "image/png",
      buffer: ONE_PIXEL_PNG,
    },
  ]);
  await expect(page.getByText("trip-notes.txt")).toBeVisible();
  await expect(page.getByText("hotel-view.png")).toBeVisible();

  await page.getByRole("button", { name: "开始规划" }).click();
  await expect(page.getByText("已生成")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText("trip-notes.txt")).toBeVisible();
  await expect(page.getByText("hotel-view.png")).toBeVisible();
});
