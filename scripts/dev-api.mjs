// 文件说明：工程脚本：dev-api。
import { spawn } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const projectRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
);
const apiRoot = path.join(projectRoot, "apps", "api");
const uvRunner = path.join(projectRoot, "scripts", "uv.mjs");

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
