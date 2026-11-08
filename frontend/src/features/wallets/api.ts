"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { backend } from "@/lib/api/http";
import { queryKeys } from "@/lib/api/query-keys";
import type { Operation, TransferRequest, Wallet, WalletArchive, WalletCreate, WalletList } from "@/lib/api/types";

export function useWallets() {
  return useQuery({ queryKey: queryKeys.wallets, queryFn: () => backend<WalletList>("wallets") });
}

/** Tras mover dinero, saldos y movimientos dejan de estar vigentes. */
function useInvalidateMoney() {
  const client = useQueryClient();
  return () =>
    Promise.all([
      client.invalidateQueries({ queryKey: queryKeys.wallets }),
      client.invalidateQueries({ queryKey: queryKeys.movementsAll }),
    ]);
}

export function useCreateWallet() {
  const invalidate = useInvalidateMoney();
  return useMutation({
    mutationFn: (body: WalletCreate) => backend<Wallet>("wallets", { method: "POST", body, idempotent: true }),
    onSuccess: invalidate,
  });
}

export function useArchiveWallet() {
  const invalidate = useInvalidateMoney();
  return useMutation({
    mutationFn: ({ walletId, moveTo }: { walletId: string; moveTo?: string }) =>
      backend<WalletArchive>(`wallets/${walletId}${moveTo ? `?move_to_wallet_id=${encodeURIComponent(moveTo)}` : ""}`, {
        method: "DELETE",
        idempotent: true,
      }),
    onSuccess: invalidate,
  });
}

export function useTransfer() {
  const invalidate = useInvalidateMoney();
  return useMutation({
    mutationFn: (body: TransferRequest) =>
      backend<Operation>("wallet-transfers", { method: "POST", body, idempotent: true }),
    onSuccess: invalidate,
  });
}
