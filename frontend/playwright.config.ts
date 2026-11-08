import { defineConfig, devices } from "@playwright/test";

/**
 * E2E contra el backend real (docker compose up en la raíz).
 * Usa Microsoft Edge instalado (channel "msedge"): no descarga navegadores.
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  fullyParallel: false,
  reporter: [["list"]],
  use: {
    baseURL: "http://localhost:3100",
    ...devices["Pixel 7"],
    channel: process.env.PW_CHANNEL ?? "msedge",
    locale: "es-PE",
    trace: "retain-on-failure",
  },
  webServer: {
    command: "npx next build && npx next start -p 3100",
    env: { MICA_NEXT_DIST_DIR: ".next-e2e" },
    url: "http://localhost:3100/login",
    reuseExistingServer: true,
    timeout: 120_000,
  },
});
