import { describe, expect, it } from "vitest";

import type { Wallet } from "@/lib/api/types";

import { isEmoji, nameError, walletTag } from "./model";

const wallet = (over: Partial<Wallet>): Wallet => ({
  id: "1", name: "Ahorro Vacaciones", role: "SAVINGS", purpose: "SAVINGS", icon: null, color: null,
  is_primary: false, is_business: false, balance: "0.00", ...over,
});

describe("nameError", () => {
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
    expect(walletTag(wallet({ role: "BUSINESS", purpose: "BUSINESS" }))).toBe("Negocio / Ventas");
    expect(walletTag(wallet({ role: "CUSTOM", purpose: "BUSINESS" }))).toBe("Negocio");
  });
  it("distingue emoji de nombre de ícono", () => {
    expect(isEmoji("☕")).toBe(true);
    expect(isEmoji("storefront")).toBe(false);
  });
});
