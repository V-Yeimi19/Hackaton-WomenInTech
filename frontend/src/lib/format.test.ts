import { describe, expect, it } from "vitest";

import { formatMoney, formatPhoneInput, formatShort, formatSigned, isPeruMobile, whenLabel } from "./format";

describe("dinero", () => {
  it("formatea con miles y dos decimales", () => {
    expect(formatMoney("1820.5")).toBe("1,820.50");
  });
  it("muestra el signo de salida", () => {
    expect(formatSigned("-12.05")).toBe("- S/ 12.05");
    expect(formatSigned(45)).toBe("S/ 45.00");
  });
  it("monto corto de la constancia", () => {
    expect(formatShort("25.00")).toBe("25");
    expect(formatShort("-12.5")).toBe("12.50");
  });
});

describe("whenLabel", () => {
  const now = new Date(2026, 10, 8, 18, 0);
  it("hoy, ayer y fecha corta", () => {
    expect(whenLabel(new Date(2026, 10, 8, 15, 42).toISOString(), now)).toBe("Hoy - 3:42 pm");
    expect(whenLabel(new Date(2026, 10, 7, 9, 5).toISOString(), now)).toBe("Ayer - 9:05 am");
    expect(whenLabel(new Date(2026, 4, 12, 10, 0).toISOString(), now)).toBe("12 May. - 10:00 am");
  });
});

describe("celular", () => {
  it("formatea mientras se escribe", () => {
    expect(formatPhoneInput("987654321999")).toBe("987 654 321");
  });
  it("valida celular peruano", () => {
    expect(isPeruMobile("987 654 321")).toBe(true);
    expect(isPeruMobile("887654321")).toBe(false);
  });
});
