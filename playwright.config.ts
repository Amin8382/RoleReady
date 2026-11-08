import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./apps/web/e2e",
  timeout: 60_000,
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: "list",
  use: { baseURL: "http://127.0.0.1:3100", trace: "retain-on-failure",
    launchOptions: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE } : undefined },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 1100 } } }],
  webServer: [
    { command: "uv run --no-sync uvicorn tests.e2e_server:app --host 127.0.0.1 --port 8001", url: "http://127.0.0.1:8001/health", reuseExistingServer: false },
    { command: "npm run start --workspace apps/web -- --port 3100", url: "http://127.0.0.1:3100", reuseExistingServer: false,
      env: { ROLEREADY_API_URL: "http://127.0.0.1:8001", ROLEREADY_AUTH_MODE: "local", ROLEREADY_ENVIRONMENT: "development" } },
  ],
});
