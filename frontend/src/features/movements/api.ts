"use client";

import { useQuery } from "@tanstack/react-query";

import { backend } from "@/lib/api/http";
import { queryKeys } from "@/lib/api/query-keys";
import type { Movement, MovementList } from "@/lib/api/types";

export function useMovements(walletId?: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.movements(walletId),
    queryFn: () => backend<MovementList>(`movements?limit=50${walletId ? `&wallet_id=${walletId}` : ""}`),
    enabled,
    refetchInterval: 5000,
    refetchOnWindowFocus: "always",
  });
}

export function useMovement(id: string) {
  return useQuery({ queryKey: queryKeys.movement(id), queryFn: () => backend<Movement>(`movements/${id}`) });
}
