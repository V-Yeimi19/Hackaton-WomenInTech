import { NextResponse } from "next/server";

import { callBackend, clearSessionCookie } from "@/lib/server/backend";

/** Revoca la sesión en el backend y borra la cookie, aunque el backend no responda. */
export async function POST() {
  await callBackend("/auth/logout", { method: "POST" }).catch(() => null);
  const response = new NextResponse(null, { status: 204 });
  clearSessionCookie(response);
  return response;
}
