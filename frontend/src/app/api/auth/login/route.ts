import { NextResponse } from "next/server";
import { z } from "zod";

import { callBackend, errorResponse, setSessionCookie } from "@/lib/server/backend";

const LoginBody = z.object({ phone: z.string().min(9).max(20) });

/** Login de demo por número: el token del backend queda en una cookie httpOnly. */
export async function POST(request: Request) {
  const parsed = LoginBody.safeParse(await request.json().catch(() => null));
  if (!parsed.success) {
    return errorResponse(422, "INVALID_PHONE", "Ingresa un celular de 9 dígitos que empiece con 9.");
  }
  let upstream: Response;
  try {
    upstream = await callBackend("/auth/phone-login", {
      method: "POST",
      token: null,
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ phone: parsed.data.phone }),
    });
  } catch {
    return errorResponse(503, "BACKEND_UNAVAILABLE", "No pudimos conectar con el servidor. Intenta de nuevo.");
  }
  const body = await upstream.json().catch(() => ({}));
  if (!upstream.ok) return NextResponse.json(body, { status: upstream.status });

  const response = NextResponse.json({ phoneMasked: body.phone_masked, isNew: body.is_new });
  setSessionCookie(response, body.session_token, body.expires_at);
  return response;
}
