// Cross-platform demo server launcher for Playwright's webServer.
// Replaces a POSIX-only `sh -c 'rm -rf /tmp/...'` one-liner so that
// `npx playwright test` also works on Windows.
import { spawn } from "node:child_process";
import { existsSync, rmSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const PORT = process.env.E2E_PORT || "8321";
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const dataDir = path.join(os.tmpdir(), "ew11-e2e");

// Prefer the repo venv (local dev); fall back to system python (CI pip install).
const venvPy = [
  path.join(root, ".venv", "Scripts", "python.exe"), // Windows venv layout
  path.join(root, ".venv", "bin", "python"), // POSIX venv layout
].find(existsSync);
const py = venvPy ?? (process.platform === "win32" ? "python" : "python3");

// Fresh demo DB every run.
rmSync(dataDir, { recursive: true, force: true });

const child = spawn(
  py,
  [
    "-m",
    "ew11_analyzer",
    "--demo",
    "--port",
    PORT,
    "--data-dir",
    dataDir,
    // demo-speed 0.15 => ~7x faster packet stream
    "--demo-speed",
    "0.15",
  ],
  { cwd: root, stdio: "inherit" },
);

child.on("error", (err) => {
  console.error(`[e2e] failed to launch python (${py}): ${err.message}`);
  process.exit(1);
});
child.on("exit", (code, signal) => process.exit(signal ? 1 : (code ?? 0)));

for (const sig of ["SIGINT", "SIGTERM", "SIGHUP"]) {
  process.on(sig, () => child.kill());
}
