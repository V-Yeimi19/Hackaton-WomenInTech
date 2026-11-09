import { expect, test } from "@playwright/test";

test("el ícono de negocio genera 10 cobros con las ventas guardadas en el perfil", async ({ page }) => {
  const phone = "9" + String(Math.floor(Math.random() * 1e8)).padStart(8, "0");
  await page.goto("/login");
  await page.getByRole("button", { name: "Iniciar sesión" }).click();
  await page.getByLabel("Número de celular").fill(phone);
  await page.getByRole("button", { name: "Ingresar" }).click();
  await expect(page).toHaveURL("/");

  type W = { id: string; name: string; role: string; balance: string };
  const wallets = async () => ((await (await page.request.get("/api/backend/wallets")).json()) as { items: W[] }).items;
  const business = (await wallets()).find((w) => w.role === "BUSINESS")!;

  // Sin perfil: avisa que falta registrar las ventas.
  const icon = page.getByRole("button", { name: `Simular yapeos para ${business.name}` });
  await icon.click();
  await expect(page.getByText("Primero registra tus ventas diarias con Mica")).toBeVisible();

  // Perfil guardado en el servidor (como lo hace el chat de Mica), sin nada en sessionStorage.
  const saved = await page.request.patch("/api/backend/agent/profile", {
    data: { wallet_id: business.id, answers: ["Bodega", "Abarrotes", "300 soles"], expected_version: 0 },
  });
  expect(saved.ok(), await saved.text()).toBeTruthy();
  expect(await page.evaluate(() => Object.keys(sessionStorage).filter((k) => k.startsWith("mica-onboarding")))).toEqual([]);

  // Doble toque rápido: solo una tanda.
  await icon.click();
  await icon.click();
  await expect.poll(async () => Number((await wallets()).find((w) => w.id === business.id)!.balance), { timeout: 20_000 })
    .toBeCloseTo(Number(business.balance) + 300, 2);
  await page.waitForTimeout(1500);
  expect(Number((await wallets()).find((w) => w.id === business.id)!.balance)).toBeCloseTo(Number(business.balance) + 300, 2);
});
