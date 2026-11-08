import "server-only";

import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { BACKEND_URL, IS_PRODUCTION, SESSION_COOKIE } from "./config";

const FORWARDED_HEADERS = ["content-type", "idempotency-key"] as const;

/** Llama al backend FastAPI con el token de la cookie (patrón BFF). */
export async function callBackend(path: string, init: RequestInit & { token?: string | null } = {}) {
  const store = await cookies();
  const token = init.token === undefined ? store.get(SESSION_COOKIE)?.value : init.token;
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  return fetch(`${BACKEND_URL}/api/v1${path}`, { ...init, headers, cache: "no-store" });
}

/** Copia solo las cabeceras que el backend necesita. */
export function forwardHeaders(source: Headers): Headers {
  const headers = new Headers();
  for (const name of FORWARDED_HEADERS) {
    const value = source.get(name);
    if (value) headers.set(name, value);
  }
  return headers;
}

/** Respuesta de error con el mismo formato que FastAPI ({code, message}). */
export function errorResponse(status: number, code: string, message: string) {
  return NextResponse.json({ code, message }, { status });
}

export function setSessionCookie(response: NextResponse, token: string, expiresAt: string) {
  response.cookies.set(SESSION_COOKIE, token, {
    httpOnly: true,
    sameSite: "lax",
    secure: IS_PRODUCTION,
    path: "/",
    expires: new Date(expiresAt),
  });
}

export function clearSessionCookie(response: NextResponse) {
  response.cookies.set(SESSION_COOKIE, "", { httpOnly: true, path: "/", maxAge: 0 });
}
