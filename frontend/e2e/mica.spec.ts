import { expect, test } from "@playwright/test";

test("Mica guarda el perfil compartido y conserva solo el historial de la app", async ({ page }) => {
  const phone = "9" + String(Math.floor(Math.random() * 1e8)).padStart(8, "0");
  await page.goto("/login");
  await page.getByRole("button", { name: "Iniciar sesión" }).click();
  await page.getByLabel("Número de celular").fill(phone);
  await page.getByRole("button", { name: "Ingresar" }).click();
  await expect(page).toHaveURL("/");
  await page.getByRole("button", { name: "Hablar con Mica, tu asesora personal", exact: true }).click();
  await expect(page).toHaveURL(/\/mica$/);

  const input = page.getByRole("textbox", { name: "Respuesta a Mica" });
  const answers = ["Cafetería", "Café y panes", "S/ 200", "Alquiler", "Viernes a las 6 p. m."];
  for (const answer of answers) {
    await expect(input).toBeEnabled();
    await input.fill(answer);
    const saved = page.waitForResponse((response) => response.url().includes("/api/backend/agent/profile") && response.request().method() === "PATCH");
    await page.getByRole("button", { name: "Enviar respuesta" }).click();
    expect((await saved).ok()).toBeTruthy();
    await expect(input).toHaveValue("");
  }
  await expect(page.getByText("Mica las recordará en la app y en Telegram.", { exact: false })).toBeVisible();
  await input.fill("Ayuda");
  await page.getByRole("button", { name: "Enviar respuesta" }).click();
  await expect(page.getByText("Escríbeme una de estas opciones:", { exact: false })).toBeVisible();
  await page.evaluate(() => sessionStorage.clear());
  await page.reload();
  await expect(page.getByText("Escríbeme una de estas opciones:", { exact: false })).toBeVisible();
  await expect(page.getByText("Mica las recordará en la app y en Telegram.", { exact: false })).toBeVisible();
  await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
  const back = page.getByRole("link", { name: "Volver al inicio", exact: true });
  const backPosition = await back.boundingBox();
  expect(backPosition?.y).toBeGreaterThanOrEqual(0);
  expect(backPosition?.y).toBeLessThan(120);
  await page.getByRole("button", { name: "Continuar en Telegram" }).click();
  await expect(page.getByRole("dialog", { name: "Habla con Mica" }).getByRole("link", { name: "Conectar con Telegram" })).toHaveAttribute("href", /^https:\/\/t\.me\/\w+\?start=[\w-]+$/);
});
