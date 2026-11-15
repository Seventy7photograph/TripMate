// 文件说明：校验 Skill Manifest 哈希基线，阻断未审核的白名单/预算变更。
import { createHash } from "node:crypto";
import { readdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const root = join(process.cwd(), "skills");
const lockPath = join(root, "manifest.lock.json");
const manifests = {};

for (const entry of readdirSync(root, { withFileTypes: true })) {
  if (!entry.isDirectory()) continue;
  const skillRoot = join(root, entry.name);
  const versionRoot = join(skillRoot, "versions");
  const candidates = [join(skillRoot, "skill.yaml")];
  try {
    for (const versionEntry of readdirSync(versionRoot, {
      withFileTypes: true,
    })) {
      if (versionEntry.isDirectory()) {
        candidates.push(join(versionRoot, versionEntry.name, "skill.yaml"));
      }
    }
  } catch {
    // Legacy single-manifest skills do not have a versions directory.
  }
  for (const path of candidates) {
    try {
      const relative = path.slice(root.length + 1).replaceAll("\\", "/");
      const content = readFileSync(path);
      manifests[relative] = createHash("sha256")
        .update(content)
        .digest("hex");
    } catch {
      // Ignore absent optional paths; actual manifests are validated by API tests.
    }
  }
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
