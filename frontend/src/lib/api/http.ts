/** Cliente HTTP del navegador: habla solo con el BFF de Next (/api/*), nunca con FastAPI. */

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string,
    readonly details?: Record<string, unknown>,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

const FALLBACK = "No pudimos completar la operación. Intenta de nuevo.";

/** Convierte una respuesta de error ({code, message, details}) en ApiError. */
export async function toApiError(response: Response): Promise<ApiError> {
  const body = (await response.json().catch(() => ({}))) as {
    code?: string;
    message?: string;
    details?: Record<string, unknown>;
  };
  return new ApiError(body.message || FALLBACK, response.status, body.code || "UNKNOWN", body.details);
}

type RequestOptions = {
  method?: "GET" | "POST" | "DELETE";
  body?: unknown;
  /** Operaciones con dinero: envía Idempotency-Key para que un reintento no cobre dos veces. */
  idempotent?: boolean;
};

export async function request<T>(url: string, { method = "GET", body, idempotent = false }: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["content-type"] = "application/json";
  if (idempotent) headers["idempotency-key"] = crypto.randomUUID();
  let response: Response;
  try {
    response = await fetch(url, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
  } catch {
    throw new ApiError("No pudimos conectar con el servidor. Intenta de nuevo.", 0, "NETWORK_ERROR");
  }
  if (response.status === 401 && typeof window !== "undefined" && !url.startsWith("/api/auth")) {
    window.location.assign("/login");
  }
  if (!response.ok) throw await toApiError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

/** Atajo para el proxy del backend. */
export const backend = <T>(path: string, options?: RequestOptions) => request<T>(`/api/backend/${path}`, options);
