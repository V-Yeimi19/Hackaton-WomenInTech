import { describe, expect, it } from "vitest";

import type { Wallet } from "@/lib/api/types";

import { isEmoji, nameError, normalizeWalletName, walletNameInput, walletTag } from "./model";

const wallet = (over: Partial<Wallet>): Wallet => ({
  id: "1", name: "Ahorro Vacaciones", role: "SAVINGS", purpose: "SAVINGS", icon: null, color: null,
  is_primary: false, is_business: false, balance: "0.00", ...over,
});

describe("nameError", () => {
  it("acepta letras con tildes y rechaza números y símbolos", () => {
    expect(nameError("Café de doña Ñora", [])).toBeNull();
    for (const name of ["Taxi 123", "Mi-ahorro", "Ahorro 🎯"]) {
      expect(nameError(name, [])).toBe("Usa solo letras y espacios.");
    }
    expect(normalizeWalletName("  taxi   familiar ")).toBe("Taxi familiar");
    expect(walletNameInput("café 123! 🎯")).toBe("Café  ");
    expect(walletNameInput("a\u0301rbol")).toBe("Árbol");
  });
  const existing = [wallet({})];
  it("valida largo y duplicados como el backend", () => {
    expect(nameError("  ", existing)).toMatch(/Escribe un nombre/);
    expect(nameError("ab", existing)).toMatch(/al menos 3/);
    expect(nameError("x".repeat(25), existing)).toMatch(/Máximo 24/);
    expect(nameError("  ahorro   vacaciones ", existing)).toMatch(/Ya tienes/);
    expect(nameError("Mi Bodega", existing)).toBeNull();
  });
});

describe("presentación", () => {
  it("etiqueta según rol y propósito", () => {
    expect(walletTag(wallet({ role: "BUSINESS", purpose: "BUSINESS" }))).toBe("Negocio");
    expect(walletTag(wallet({ role: "CUSTOM", purpose: "BUSINESS" }))).toBe("Negocio");
  });
  it("distingue emoji de nombre de ícono", () => {
    expect(isEmoji("☕")).toBe(true);
    expect(isEmoji("storefront")).toBe(false);
  });
});
