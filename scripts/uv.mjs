// 文件说明：工程脚本：uv。
import { spawnSync } from "node:child_process";

const args = process.argv.slice(2);
const candidates = [
  { command: process.env.UV_BIN || "uv", args },
  { command: process.env.PYTHON || "python", args: ["-m", "uv", ...args] },
];

for (const candidate of candidates) {
  const result = spawnSync(candidate.command, candidate.args, {
    stdio: "inherit",
    shell: false,
  });
  if (result.error?.code === "ENOENT") {
    continue;
  }
  if (result.error) {
    console.error(result.error.message);
    process.exit(1);
  }
  process.exit(result.status ?? 1);
}

console.error("uv is required. Install uv or the Python uv package.");
process.exit(127);
