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
    // fresh demo DB every run; demo-speed 0.15 => ~7x faster packet stream
    command: `sh -c 'rm -rf /tmp/ew11-e2e && exec ../.venv/bin/python -m ew11_analyzer --demo --port ${PORT} --data-dir /tmp/ew11-e2e --demo-speed 0.15'`,
    url: `${BASE}/api/status`,
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
});
