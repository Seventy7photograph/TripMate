// 文件说明：校验 Skill Manifest 哈希基线，阻断未审核的白名单/预算变更。
import { createHash } from "node:crypto";
import { readdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const root = join(process.cwd(), "skills");
const lockPath = join(root, "manifest.lock.json");
const manifests = {};

for (const entry of readdirSync(root, { withFileTypes: true })) {
  if (!entry.isDirectory()) continue;
  const relative = `${entry.name}/skill.yaml`;
  const content = readFileSync(join(root, relative));
  manifests[relative] = createHash("sha256").update(content).digest("hex");
}

const payload = {
  algorithm: "sha256",
  manifests: Object.fromEntries(
    Object.entries(manifests).sort(([left], [right]) => left.localeCompare(right)),
  ),
};
const expected = `${JSON.stringify(payload, null, 2)}\n`;

if (process.argv.includes("--write")) {
  writeFileSync(lockPath, expected, "utf8");
  console.log(`已写入 ${Object.keys(manifests).length} 个 Skill Manifest 哈希`);
  process.exit(0);
}

const actual = readFileSync(lockPath, "utf8");
if (actual !== expected) {
  console.error("Skill Manifest 与 manifest.lock.json 不一致。");
  console.error("审核 manifest 变更后执行：node scripts/check-skill-manifests.mjs --write");
  process.exit(1);
}

console.log(`Skill Manifest 哈希校验通过：${Object.keys(manifests).length} files`);
