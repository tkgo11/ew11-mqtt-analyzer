import { defineConfig } from "@playwright/test";

const PORT = 8321;
const BASE = `http://127.0.0.1:${PORT}`;

export default defineConfig({
  testDir: "./tests",
  timeout: 90_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: 1,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: BASE,
    trace: "retain-on-failure",
  },
  webServer: {
    // serve.mjs is cross-platform (no POSIX shell, no /tmp): it wipes a fresh
    // demo DB under os.tmpdir() and prefers the repo venv python.
    command: "node serve.mjs",
    env: { E2E_PORT: String(PORT) },
    url: `${BASE}/api/status`,
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
});
