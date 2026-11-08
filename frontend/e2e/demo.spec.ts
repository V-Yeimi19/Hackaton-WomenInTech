import { expect, test, type Page } from "@playwright/test";

type Wallet = { id: string; name: string; role: string; balance: string };
type Movement = { id: string; title: string; amount: string; operation_number: string; security_code: string; category: string | null; direction: string; note: string | null };

const randomPhone = () => "9" + String(Math.floor(Math.random() * 1e8)).padStart(8, "0");

/** Lee el servidor a través del BFF (misma cookie httpOnly que usa la app). */
async function api<T>(page: Page, path: string): Promise<T> {
  const response = await page.request.get(`/api/backend/${path}`);
  expect(response.ok()).toBeTruthy();
  return (await response.json()) as T;
}
const wallets = async (page: Page) => (await api<{ items: Wallet[] }>(page, "wallets")).items;
const lastMovement = async (page: Page) => (await api<{ items: Movement[] }>(page, "movements?limit=1")).items[0];

async function login(page: Page, phone: string) {
  await page.goto("/login");
  await page.getByRole("button", { name: "Iniciar sesión" }).click();
  await page.getByLabel("Número de celular").fill(phone);
  await page.getByRole("button", { name: "Ingresar" }).click();
  await expect(page).toHaveURL("/");
}

test("sin sesión redirige al login y valida el número", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/login$/);
  await page.getByRole("button", { name: "Iniciar sesión" }).click();
  await page.getByLabel("Número de celular").fill("812345678");
  await page.getByRole("button", { name: "Ingresar" }).click();
  await expect(page.getByText("Ingresa un celular de 9 dígitos que empiece con 9.")).toBeVisible();
});

test("recorrido completo de la demo contra el backend", async ({ page, context }) => {
  const phone = randomPhone();
  await login(page, phone);

  // La cookie de sesión es httpOnly: el JavaScript del navegador no la ve.
  const cookie = (await context.cookies()).find((c) => c.name === "mica_token");
  expect(cookie?.httpOnly).toBe(true);
  expect(await page.evaluate(() => document.cookie)).not.toContain("mica_token");

  // Saldos ocultos por defecto; el ojito muestra el saldo real del servidor.
  const initial = await wallets(page);
  const principal = initial.find((w) => w.role === "PRINCIPAL")!;
  const business = initial.find((w) => w.role === "BUSINESS")!;
  const savings = initial.find((w) => w.role === "SAVINGS")!;
  const principalCard = page.locator(`[data-wallet="${principal.id}"]`);
  await expect(principalCard.getByTestId("wallet-balance")).toHaveText("****");
  await principalCard.getByRole("button", { name: "Mostrar saldo" }).click();
  await expect(principalCard.getByTestId("wallet-balance")).toHaveText(Number(principal.balance).toLocaleString("en-US", { minimumFractionDigits: 2 }));

  // Yapeo desde el negocio con categoría -> constancia con los datos del servidor.
  await page.getByRole("button", { name: "Yapear", exact: true }).click();
  await page.locator('[data-wallet-option="BUSINESS"]').click();
  await expect(page).toHaveURL(/\/yapear/);
  for (const key of ["1", "2", ".", "0", "5"]) await page.locator(`[data-key="${key}"]`).click();
  await page.locator('[data-category="RESTOCK"]').click();
  await expect(page.getByLabel("Agregar mensaje")).toHaveAttribute("readonly", "");
  await page.getByTestId("pay").click();
  await expect(page).toHaveURL(/\/constancia\//);
  const yapeo = await lastMovement(page);
  expect(yapeo).toMatchObject({ amount: "-12.05", category: "RESTOCK", title: "Yapeo a Lucía Gómez R." });
  await expect(page.getByTestId("receipt-amount")).toHaveText("12.05");
  await expect(page.getByText(yapeo.operation_number)).toBeVisible();
  await expect(page.getByTestId("security-code")).toHaveText(yapeo.security_code.split("").join(""));
  const afterYapeo = await wallets(page);
  expect((Number(business.balance) - Number(afterYapeo.find((w) => w.id === business.id)!.balance)).toFixed(2)).toBe("12.05");

  // Límite de S/ 500 por yapeo.
  await page.getByRole("button", { name: "Nuevo yapeo" }).click();
  await page.locator('[data-wallet-option="PRINCIPAL"]').click();
  for (const key of ["6", "0", "0"]) await page.locator(`[data-key="${key}"]`).click();
  await page.getByTestId("pay").click();
  await expect(page.getByRole("status")).toContainText("500");
  await page.getByRole("button", { name: "Cerrar" }).click();

  // Transferencia entre billeteras con descripción.
  await page.getByRole("button", { name: "Transferir" }).click();
  const sheet = page.getByRole("dialog", { name: "Transferir" });
  await sheet.getByRole("button", { name: /Elige una billetera/ }).first().click();
  await sheet.getByRole("option", { name: new RegExp(business.name) }).click();
  await sheet.getByRole("button", { name: /Elige una billetera/ }).click();
  await sheet.getByRole("option", { name: new RegExp(savings.name) }).click();
  await sheet.getByLabel("Monto").fill("10");
  await sheet.getByLabel("Descripción").fill("Prueba E2E");
  await sheet.getByRole("button", { name: /Transferir S\// }).click();
  await expect(sheet).toBeHidden();
  const transfer = await lastMovement(page);
  expect(transfer).toMatchObject({ direction: "TRANSFER", note: "Prueba E2E", amount: "10.00" });

  // Pago con QR desde la Principal.
  await page.getByRole("link", { name: "Escanear QR" }).click();
  await page.getByRole("button", { name: "Simular escaneo de QR" }).click();
  await page.locator('[data-wallet-option="PRINCIPAL"]').click();
  await page.locator('[data-key="7"]').click();
  await page.getByTestId("pay").click();
  await expect(page).toHaveURL(/\/constancia\//);
  expect(await lastMovement(page)).toMatchObject({ title: "Yapeo a La Tiendita de Don Pepe", amount: "-7.00", category: null });
  await page.getByRole("button", { name: "Cerrar" }).click();

  // Crear y eliminar una billetera.
  await page.getByRole("link", { name: /Nueva Billetera/ }).click();
  await page.getByLabel("Nombre").fill("Mi Bodega E2E");
  await page.getByRole("button", { name: "Crear billetera" }).click();
  await expect(page).toHaveURL("/");
  const created = (await wallets(page)).find((w) => w.name === "Mi Bodega E2E")!;
  expect(created.balance).toBe("0.00");
  await page.locator(`[data-wallet="${created.id}"]`).getByRole("button", { name: "Opciones de billetera" }).click();
  await page.getByRole("button", { name: /Eliminar billetera/ }).click();
  await page.getByRole("button", { name: "Eliminar", exact: true }).click();
  await expect.poll(async () => (await wallets(page)).some((w) => w.id === created.id)).toBe(false);

  // Movimientos: el yapeo abre su constancia con el mismo número de operación.
  await page.getByRole("button", { name: "Mostrar movimientos" }).click();
  const row = page.getByRole("button", { name: "Ver detalle: Yapeo a Lucía Gómez R." });
  await expect(row).toContainText("Para volver a surtir");
  await row.click();
  await expect(page.getByText(yapeo.operation_number)).toBeVisible();
  await page.getByRole("button", { name: "Cerrar" }).click();

  // Cerrar sesión revoca la sesión; el mismo número vuelve a sus datos.
  const before = await wallets(page);
  await page.getByRole("button", { name: "Mi perfil" }).click();
  await page.getByRole("button", { name: "Cerrar sesión" }).click();
  await expect(page).toHaveURL(/\/login$/);
  expect((await page.request.get("/api/backend/wallets")).status()).toBe(401);
  await login(page, phone);
  expect((await wallets(page)).map((w) => w.balance)).toEqual(before.map((w) => w.balance));
});

test("cada número tiene datos distintos", async ({ browser }) => {
  const balances = [];
  for (const phone of [randomPhone(), randomPhone()]) {
    const page = await (await browser.newContext()).newPage();
    await login(page, phone);
    balances.push((await wallets(page)).map((w) => w.balance).join("|"));
  }
  expect(balances[0]).not.toBe(balances[1]);
});
