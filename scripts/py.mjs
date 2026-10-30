// Runs Python from backend/.venv for the npm scripts in package.json, so nobody
// has to activate the venv. No npm packages: this uses only Node built-ins.
//
//   node scripts/py.mjs setup        create backend/.venv and install requirements
//   node scripts/py.mjs <args...>    run the venv's python with <args> in backend/

import { spawn, spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const BACKEND = join(dirname(fileURLToPath(import.meta.url)), "..", "backend");
const VENV = join(BACKEND, ".venv");
const WINDOWS = process.platform === "win32";
const VENV_PYTHON = WINDOWS ? join(VENV, "Scripts", "python.exe") : join(VENV, "bin", "python");
const VERSION_CHECK = "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)";

function fail(message) {
  console.error(message);
  process.exit(1);
}

function runSync(cmd, args) {
  const result = spawnSync(cmd, args, { cwd: BACKEND, stdio: "inherit" });
  if (result.status !== 0) process.exit(result.status ?? 1);
}

// First interpreter on PATH that is Python 3.11 or newer. Set PYTHON to pick one.
function findSystemPython() {
  const candidates = [
    process.env.PYTHON && [process.env.PYTHON],
    ["python3"],
    ["python"],
    WINDOWS && ["py", "-3"],
  ].filter(Boolean);
  for (const [cmd, ...args] of candidates) {
    const result = spawnSync(cmd, [...args, "-c", VERSION_CHECK], { stdio: "ignore" });
    if (result.status === 0) return [cmd, ...args];
  }
  return fail("Python 3.11 or newer not found. Install it, or set PYTHON to its path.");
}

function setup() {
  if (!existsSync(VENV_PYTHON)) {
    const [cmd, ...args] = findSystemPython();
    console.log("Creating backend/.venv");
    runSync(cmd, [...args, "-m", "venv", ".venv"]);
  } else if (spawnSync(VENV_PYTHON, ["-c", VERSION_CHECK]).status !== 0) {
    fail("backend/.venv is older than Python 3.11. Delete it and run `npm run setup` again.");
  }
  runSync(VENV_PYTHON, ["-m", "pip", "install", "-r", "requirements.txt", "-r", "requirements-dev.txt"]);
}

const args = process.argv.slice(2);

if (args[0] === "setup") {
  setup();
} else {
  if (!existsSync(VENV_PYTHON)) fail("backend/.venv not found. Run `npm run setup` first.");
  const child = spawn(VENV_PYTHON, args, { cwd: BACKEND, stdio: "inherit" });
  // Ctrl+C reaches the child too. Let it shut down (uvicorn, http.server), then exit with its code.
  process.on("SIGINT", () => {});
  // A stop button or `kill` reaches only this process, so pass it on.
  process.on("SIGTERM", () => child.kill("SIGTERM"));
  child.on("error", (err) => fail(`Could not start ${VENV_PYTHON}: ${err.message}`));
  child.on("exit", (code, signal) => process.exit(code ?? (signal ? 1 : 0)));
}
