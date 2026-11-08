import { expect, test, type Page } from "@playwright/test";

const phone = () => "9" + String(Math.floor(Math.random() * 1e8)).padStart(8, "0");

async function signIn(page: Page, number: string) {
  await page.getByRole("button", { name: "Iniciar sesión" }).click();
  await page.getByLabel("Número de celular").fill(number);
  await page.getByRole("button", { name: "Ingresar", exact: true }).click();
  // Sin recargar ni navegar manualmente después del envío.
  await expect(page).toHaveURL("/");
  await expect(page.getByRole("button", { name: "Hablar con Mica, tu asesora personal", exact: true })).toBeVisible();
  const response = await page.request.get("/api/backend/me");
  expect(response.status()).toBe(200);
  return response.json() as Promise<{ user_id: string }>;
}

test("iniciar sesión abre Inicio inmediatamente y permite cambiar de cuenta", async ({ page }) => {
  // Entrar por una ruta protegida provoca la redirección previa al login.
  await page.goto("/mica");
  await expect(page).toHaveURL(/\/login$/);
  const first = await signIn(page, phone());

  await page.getByRole("button", { name: "Mi perfil", exact: true }).click();
  await page.getByRole("button", { name: "Cerrar sesión" }).click();
  await expect(page).toHaveURL(/\/login$/);
  const second = await signIn(page, phone());
  expect(second.user_id).not.toBe(first.user_id);
});
