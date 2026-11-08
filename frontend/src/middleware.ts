import { NextResponse, type NextRequest } from "next/server";

const SESSION_COOKIE = "mica_token";

/** Sin sesión todo redirige a /login; con sesión, /login lleva a Inicio. */
export function middleware(request: NextRequest) {
  const hasSession = Boolean(request.cookies.get(SESSION_COOKIE)?.value);
  const isLogin = request.nextUrl.pathname === "/login";
  if (!hasSession && !isLogin) return NextResponse.redirect(new URL("/login", request.url));
  if (hasSession && isLogin) return NextResponse.redirect(new URL("/", request.url));
  return NextResponse.next();
}

export const config = {
  // Excluye la API (BFF) y los archivos estáticos.
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico|mica-avatar.jpg).*)"],
};
