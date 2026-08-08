import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.E2E_BASE_URL ?? "http://localhost:3000";

export default defineConfig({
  testDir: "./e2e",
  globalSetup: "./e2e/global-setup.ts",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 1,
  workers: 1,
  timeout: 120_000,
  reporter: [
    ["html", { outputFolder: "playwright-report" }],
    ["list"],
  ],
  use: {
    baseURL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "setup",
      testMatch: /auth\.setup\.ts/,
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "chromium",
      dependencies: ["setup"],
      testIgnore: /auth\.setup\.ts|responsive\.spec\.ts|accessibilite\.spec\.ts/,
      use: {
        ...devices["Desktop Chrome"],
        storageState: ".auth/owner.json",
      },
    },
    {
      name: "firefox",
      dependencies: ["setup"],
      testIgnore: /auth\.setup\.ts|responsive\.spec\.ts|accessibilite\.spec\.ts/,
      use: {
        ...devices["Desktop Firefox"],
        storageState: ".auth/owner.json",
      },
    },
    {
      name: "webkit",
      dependencies: ["setup"],
      testIgnore: /auth\.setup\.ts|responsive\.spec\.ts|accessibilite\.spec\.ts/,
      use: {
        ...devices["Desktop Safari"],
        storageState: ".auth/owner.json",
      },
    },
    {
      name: "responsive",
      testMatch: /responsive\.spec\.ts/,
      use: { ...devices["iPhone 13"] },
    },
    {
      name: "accessibilite",
      testMatch: /accessibilite\.spec\.ts/,
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: process.env.CI
    ? undefined
    : {
        command: "npm run dev",
        url: baseURL,
        reuseExistingServer: true,
        timeout: 60_000,
      },
});
