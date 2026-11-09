import { expect, test } from "@playwright/test";

test("cada toque del ícono de negocio genera 10 yapeos con las ventas que Mica conoce", async ({ page }) => {
  const phone = "9" + String(Math.floor(Math.random() * 1e8)).padStart(8, "0");
  await page.goto("/login");
  await page.getByRole("button", { name: "Iniciar sesión" }).click();
  await page.getByLabel("Número de celular").fill(phone);
  await page.getByRole("button", { name: "Ingresar" }).click();
  await expect(page).toHaveURL("/");

  type W = { id: string; name: string; role: string; balance: string };
  const wallets = async () => ((await (await page.request.get("/api/backend/wallets")).json()) as { items: W[] }).items;
  const business = (await wallets()).find((w) => w.role === "BUSINESS")!;

  // Sin promedio en el perfil: igual genera 10 yapeos con la referencia de S/ 300, sin avisos.
  const icon = page.getByRole("button", { name: `Simular yapeos para ${business.name}` });
  const balanceOf = async () => Number((await wallets()).find((w) => w.id === business.id)!.balance);
  const start = Number(business.balance);
  await icon.click();
  await expect.poll(balanceOf, { timeout: 30_000 }).toBeCloseTo(start + 300, 2);
  await expect(page.getByText("Primero registra tus ventas diarias")).toHaveCount(0);

  // Perfil guardado en el servidor (como lo hace el chat de Mica), sin nada en sessionStorage.
  const saved = await page.request.patch("/api/backend/agent/profile", {
    data: { wallet_id: business.id, answers: ["Bodega", "Abarrotes", "500 soles"], expected_version: 0 },
  });
  expect(saved.ok(), await saved.text()).toBeTruthy();
  expect(await page.evaluate(() => Object.keys(sessionStorage).filter((k) => k.startsWith("mica-onboarding")))).toEqual([]);

  // Con el promedio que Mica conoce (S/ 500): cada toque suma 10 yapeos; dos toques seguidos, 20.
  const before = (await page.request.get("/api/backend/movements?limit=100").then((r) => r.json())).items.length as number;
  await icon.click();
  await icon.click();
  await expect.poll(balanceOf, { timeout: 30_000 }).toBeCloseTo(start + 300 + 1000, 2);
  await page.waitForTimeout(1500);
  expect(await balanceOf()).toBeCloseTo(start + 300 + 1000, 2);
  const after = (await page.request.get("/api/backend/movements?limit=100").then((r) => r.json())).items.length as number;
  expect(after - before).toBe(20);

  // Sin efectos visuales al tocarlo ni al pasar el mouse.
  await icon.hover();
  const style = await icon.evaluate((el) => {
    const css = getComputedStyle(el);
    return { outline: css.outlineStyle, transform: css.transform, cursor: css.cursor };
  });
  expect(style).toEqual({ outline: "none", transform: "none", cursor: "default" });
});
