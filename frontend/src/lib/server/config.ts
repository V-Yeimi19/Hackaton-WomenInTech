import "server-only";

/**
 * Configuración del lado servidor (BFF). Nunca se expone al navegador:
 * el token de sesión vive en una cookie httpOnly y solo Next habla con FastAPI.
 */
export const BACKEND_URL = (process.env.MICA_API_URL ?? "http://localhost:8000").replace(/\/+$/, "");
export const SESSION_COOKIE = "mica_token";
export const IS_PRODUCTION = process.env.NODE_ENV === "production";
