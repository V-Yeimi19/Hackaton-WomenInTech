import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, request, toApiError } from "./http";

afterEach(() => vi.restoreAllMocks());

describe("cliente HTTP", () => {
  it("convierte el error del backend en ApiError con su mensaje", async () => {
    const response = new Response(JSON.stringify({ code: "DAILY_LIMIT", message: "Superas el límite diario", details: { remaining: "40.00" } }), { status: 422 });
    const error = await toApiError(response);
    expect(error).toBeInstanceOf(ApiError);
    expect(error.code).toBe("DAILY_LIMIT");
    expect(error.details?.remaining).toBe("40.00");
  });

  it("envía Idempotency-Key en operaciones con dinero", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("{}", { status: 201 }));
    await request("/api/backend/yapeos", { method: "POST", body: { amount: "1.00" }, idempotent: true });
    const headers = fetchMock.mock.calls[0][1]?.headers as Record<string, string>;
    expect(headers["idempotency-key"]).toMatch(/[0-9a-f-]{36}/);
  });

  it("los errores de red se reportan en español", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("fetch failed"));
    await expect(request("/api/backend/wallets")).rejects.toMatchObject({ code: "NETWORK_ERROR" });
  });
});
