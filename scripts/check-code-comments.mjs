// 文件说明：校验所有手写代码文件是否包含中文“文件说明”头注释。
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";

const extensions = new Set([
  ".css",
  ".html",
  ".js",
  ".mako",
  ".mjs",
  ".ps1",
  ".py",
  ".scss",
  ".ts",
  ".vue",
]);

const listed = execFileSync(
  "git",
  ["ls-files", "--cached", "--others", "--exclude-standard"],
  { encoding: "utf8" },
)
  .split(/\r?\n/)
  .filter(Boolean)
  .filter((file) => extensions.has(file.slice(file.lastIndexOf("."))));

const missing = listed.filter((file) => {
  const header = readFileSync(file, "utf8").split(/\r?\n/, 5).join("\n");
  return !header.includes("文件说明");
});

if (missing.length > 0) {
  console.error("以下代码文件缺少中文“文件说明”头注释：");
  console.error(missing.join("\n"));
  process.exit(1);
}

console.log(`代码文件说明检查通过：${listed.length} files`);
