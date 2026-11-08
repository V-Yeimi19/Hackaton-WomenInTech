"use client";

import { useQuery } from "@tanstack/react-query";

import { backend } from "@/lib/api/http";
import { queryKeys } from "@/lib/api/query-keys";
import type { LinkChallenge, Me } from "@/lib/api/types";

/** Perfil de la sesión. Con `watch`, se consulta cada 3 s (p. ej. esperando el vínculo con Telegram). */
export function useMe({ watch = false }: { watch?: boolean } = {}) {
  return useQuery({
    queryKey: queryKeys.me,
    queryFn: () => backend<Me>("me"),
    refetchInterval: watch ? 3000 : false,
  });
}

/**
 * Código de un solo uso para vincular Telegram (vence a los 10 min). Se pide al abrir
 * la hoja y no se reutiliza entre aperturas; no se renueva al volver de Telegram.
 */
export function useTelegramLink(enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.telegramLink,
    queryFn: () => backend<LinkChallenge>("channel-link-challenges", { method: "POST" }),
    enabled,
    gcTime: 0,
    staleTime: 9 * 60 * 1000,
    refetchOnWindowFocus: false,
    retry: 1,
  });
}
