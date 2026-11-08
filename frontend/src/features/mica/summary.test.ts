import { describe, expect, it } from "vitest";
import type { Movement } from "@/lib/api/types";
import { summarizeToday } from "./summary";

function movement(overrides: Partial<Movement> = {}): Movement {
  return {
    id: "sale", operation_number: "1", security_code: "000", kind: "SALE", direction: "IN", title: "Venta", amount: "10.10",
    occurred_at: "2026-11-08T15:00:00Z",
    wallets: [{ id: "business", name: "Café", role: "BUSINESS", purpose: "BUSINESS", delta: "10.10" }],
    ...overrides,
  };
}

describe("resumen de movimientos de Mica", () => {
  const now = new Date("2026-11-09T02:00:00Z"); // Todavía es domingo 8 en Lima.
  it("suma cobros del día de Lima sin aportes ni movimientos de otra billetera", () => {
    const rows = [movement(), movement({ id: "second", wallets: [{ id: "business", name: "Café", role: "BUSINESS", purpose: "BUSINESS", delta: "0.20" }] }),
      movement({ kind: "OWNER_CONTRIBUTION" }), movement({ occurred_at: "2026-11-08T04:59:59Z" }),
      movement({ wallets: [{ id: "other", name: "Otra", role: "BUSINESS", purpose: "BUSINESS", delta: "900.00" }] })];
    expect(summarizeToday(rows, "business", now)).toEqual({ collected: "10.30", transferred: "0.00" });
  });
  it("cuenta solo transferencias que salen del negocio hacia la principal", () => {
    const transfer = movement({ kind: "WALLET_TRANSFER", direction: "TRANSFER", from_wallet: { id: "business", name: "Café" }, to_wallet: { id: "main", name: "Principal" }, wallets: [
      { id: "business", name: "Café", role: "BUSINESS", purpose: "BUSINESS", delta: "-100.00" },
      { id: "main", name: "Principal", role: "PRINCIPAL", purpose: "PERSONAL", delta: "100.00" },
    ] });
    expect(summarizeToday([transfer, { ...transfer, from_wallet: { id: "main", name: "Principal" } }], "business", now)).toEqual({ collected: "0.00", transferred: "100.00" });
    expect(summarizeToday([], "business", now)).toEqual({ collected: "0.00", transferred: "0.00" });
  });
});
