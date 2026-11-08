import { describe, expect, it } from "vitest";
import { dailySalesCents, demoPayments } from "./demo-payments";

describe("yapeos basados en el promedio declarado", () => {
  it.each([
    ["Menos de S/ 100", 5000], ["S/ 100 – S/ 300", 20000],
    ["S/ 300 – S/ 500", 40000], ["Más de S/ 500", 60000],
    ["S/ 150", 15000], ["de 100 a 200 soles", 15000],
    ["S/ 1,000.50", 100050], ["150,50 soles", 15050],
    ["", null], ["no sé", null], ["-100", null], ["0", null],
  ])("interpreta %s", (text, expected) => expect(dailySalesCents(text)).toBe(expected));

  it.each([10, 101, 5000, 15050, 20000, 60000])("reparte %i céntimos sin cambiar el total", (total) => {
    const payments = demoPayments(total);
    expect(payments).toHaveLength(10);
    const amounts = payments.map(({ amount }) => Math.round(Number(amount) * 100));
    expect(amounts.every((amount) => amount > 0)).toBe(true);
    expect(amounts.reduce((sum, amount) => sum + amount, 0)).toBe(total);
  });
});
