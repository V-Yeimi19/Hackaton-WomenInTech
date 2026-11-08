import { NextResponse } from "next/server";

import { callBackend, clearSessionCookie, errorResponse, forwardHeaders } from "@/lib/server/backend";

/**
 * Proxy BFF hacia FastAPI: el navegador llama a /api/backend/* y Next agrega el
 * token desde la cookie httpOnly. Solo se permiten las rutas que usa la app.
 */
const ALLOWED = [/^wallets(\/[\w-]+)?$/, /^wallet-transfers$/, /^yapeos$/, /^movements(\/[\w-]+)?$/, /^me$/, /^channel-link-challenges$/];

type Context = { params: Promise<{ path: string[] }> };

async function proxy(request: Request, { params }: Context) {
  const { path } = await params;
  const target = path.join("/");
  if (!ALLOWED.some((rule) => rule.test(target))) {
    return errorResponse(404, "NOT_FOUND", "Ruta no disponible.");
  }
  const search = new URL(request.url).search;
  const hasBody = !["GET", "HEAD"].includes(request.method);
  let upstream: Response;
  try {
    upstream = await callBackend(`/${target}${search}`, {
      method: request.method,
      headers: forwardHeaders(request.headers),
      body: hasBody ? await request.text() : undefined,
    });
  } catch {
    return errorResponse(503, "BACKEND_UNAVAILABLE", "No pudimos conectar con el servidor. Intenta de nuevo.");
  }
  if (upstream.status === 204) return new NextResponse(null, { status: 204 });
  const body = await upstream.json().catch(() => ({}));
  const response = NextResponse.json(body, { status: upstream.status });
  if (upstream.status === 401) clearSessionCookie(response);
  return response;
}

export { proxy as DELETE, proxy as GET, proxy as PATCH, proxy as POST };
