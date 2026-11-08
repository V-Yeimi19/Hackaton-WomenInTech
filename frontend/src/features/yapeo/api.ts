"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { backend } from "@/lib/api/http";
import { queryKeys } from "@/lib/api/query-keys";
import type { Operation, YapeoRequest } from "@/lib/api/types";

export function useYapeo() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: YapeoRequest) => backend<Operation>("yapeos", { method: "POST", body, idempotent: true }),
    onSuccess: (operation) => {
      // La respuesta ya trae saldos y constancia: se siembra la caché sin otra llamada.
      client.setQueryData(queryKeys.wallets, operation.wallets);
      client.setQueryData(queryKeys.movement(operation.movement.id), operation.movement);
      return client.invalidateQueries({ queryKey: queryKeys.movementsAll });
    },
  });
}
