import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "node",
    include: ["tests/**/*.test.ts"],
    // Playwright specs live under tests/e2e and are run by `npm run e2e`.
    exclude: ["tests/e2e/**", "node_modules/**"],
  },
});
