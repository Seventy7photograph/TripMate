// 文件说明：工程脚本：dev-api。
import { spawn } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const projectRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
);
const apiRoot = path.join(projectRoot, "apps", "api");
const uvRunner = path.join(projectRoot, "scripts", "uv.mjs");
const envPath = path.join(projectRoot, ".env");

if (existsSync(envPath)) {
  for (const line of readFileSync(envPath, "utf8").split(/\r?\n/)) {
    const match = line.match(/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$/);
    if (!match || process.env[match[1]] !== undefined) continue;
    process.env[match[1]] = match[2].replace(/^['"]|['"]$/g, "");
  }
}

const commands = [
  ["run", "--project", ".", "python", "run.py", "--reload"],
  [
    "run",
    "--project",
    ".",
    "python",
    "-m",
    "app.workers.planning_worker",
  ],
];

if (process.env.MCP_GATEWAY_ENABLED === "true") {
  commands.push(
    [
      "run",
      "--project",
      ".",
      "python",
      "-m",
      "app.mcp.server",
      "--connector",
      "amap",
      "--port",
      process.env.MCP_AMAP_PORT ?? "8021",
    ],
    [
      "run",
      "--project",
      ".",
      "python",
      "-m",
      "app.mcp.server",
      "--connector",
      "weather",
      "--port",
      process.env.MCP_WEATHER_PORT ?? "8022",
    ],
  );
}

const children = commands.map((args) =>
  spawn(process.execPath, [uvRunner, ...args], {
    cwd: apiRoot,
    env: process.env,
    stdio: "inherit",
  }),
);

let stopping = false;

function stop(exitCode = 0) {
  if (stopping) return;
  stopping = true;
  for (const child of children) {
    if (!child.killed) child.kill();
  }
  process.exitCode = exitCode;
}

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => stop());
}

for (const child of children) {
  child.on("error", (error) => {
    console.error(error);
    stop(1);
  });
  child.on("exit", (code) => {
    if (!stopping) stop(code ?? 1);
  });
}
