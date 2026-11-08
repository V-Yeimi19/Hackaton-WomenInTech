import { describe, expect, it } from "vitest";

import { allowsCategories, amountError, pressKey, type Key } from "./model";

const type = (keys: Key[], start = "0") => keys.reduce(pressKey, start);

describe("pressKey", () => {
  it("reemplaza el cero inicial y acumula dígitos", () => {
    expect(type(["1", "2"])).toBe("12");
  });
  it("admite un solo punto y como máximo dos decimales", () => {
    expect(type(["1", "2", ".", "0", "5", "9", "."])).toBe("12.05");
  });
  it("limita la parte entera a 4 dígitos", () => {
    expect(type(["9", "9", "9", "9", "9"])).toBe("9999");
  });
  it("borrar hasta vaciar deja 0", () => {
    expect(type(["7", "backspace", "backspace"])).toBe("0");
  });
});

describe("amountError", () => {
  it("exige un monto positivo", () => {
    expect(amountError(0, 100)).toMatch(/mayor a S\/ 0/);
  });
  it("aplica el límite de S/ 500 por yapeo", () => {
    expect(amountError(500.01, 9999)).toBe("Límite por yapeo: S/ 500");
    expect(amountError(500, 9999)).toBeNull();
  });
  it("no deja yapear más que el saldo", () => {
    expect(amountError(50, 20)).toMatch(/Disponible: S\/ 20.00/);
  });
});

describe("allowsCategories", () => {
  it("solo en billeteras de negocio", () => {
    expect(allowsCategories({ is_business: true })).toBe(true);
    expect(allowsCategories({ is_business: false })).toBe(false);
    expect(allowsCategories(undefined)).toBe(false);
  });
});
