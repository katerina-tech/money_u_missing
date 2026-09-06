import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end configuration.
 *
 * Assumes the API is already running on :8000 (`make dev-api`) and starts the
 * frontend itself. The API is not started here on purpose: these tests are
 * about the two halves agreeing, and silently starting a backend would hide a
 * misconfiguration that a reviewer needs to see.
 */
export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "list" : [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  // A production build rather than the dev server: it is what actually ships,
  // and it removes on-demand compilation as a source of timing variance in the
  // results.
  webServer: process.env.E2E_BASE_URL
    ? undefined
    : {
        command: "npm run build && npm run start",
        url: "http://localhost:3000",
        reuseExistingServer: false,
        timeout: 180_000,
      },
});
