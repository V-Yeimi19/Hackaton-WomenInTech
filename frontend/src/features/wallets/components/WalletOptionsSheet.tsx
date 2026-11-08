"use client";

import { useState } from "react";

import { BottomSheet } from "@/components/ui/BottomSheet";
import { Icon } from "@/components/ui/Icon";
import { useToast } from "@/components/ui/Toast";
import type { Wallet } from "@/lib/api/types";
import { formatMoney } from "@/lib/format";

import { useArchiveWallet } from "../api";
import { WalletAvatar } from "./WalletAvatar";
import { WalletSelect } from "./WalletSelect";

type Props = { wallet: Wallet | null; wallets: Wallet[]; onClose: () => void };

/**
 * Menú ⋮ de una billetera: eliminar con validaciones.
 * Sin saldo: confirma y avisa de sus movimientos. Con saldo: exige moverlo a otra billetera.
 */
export function WalletOptionsSheet({ wallet, wallets, onClose }: Props) {
  const toast = useToast();
  const archive = useArchiveWallet();
  const [view, setView] = useState<"menu" | "delete">("menu");
  const [destination, setDestination] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  function close() {
    setView("menu"); setDestination(null); setError(null);
    onClose();
  }
  if (!wallet) return null;
  const hasMoney = Number(wallet.balance) > 0;
  const others = wallets.filter((w) => w.id !== wallet.id);

  async function confirm() {
    if (!wallet) return;
    if (hasMoney && !destination) return setError("Elige a qué billetera mover tu saldo antes de eliminarla.");
    try {
      await archive.mutateAsync({ walletId: wallet.id, moveTo: destination ?? undefined });
      const name = wallet.name;
      close();
      toast(`Billetera "${name}" eliminada`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No pudimos eliminar la billetera.");
    }
  }

  return (
    <BottomSheet open onClose={close} title={view === "menu" ? wallet.name : undefined}>
      {view === "menu" ? (
        <>
          <div className="mb-4 flex items-center gap-3">
            <WalletAvatar wallet={wallet} />
            <p className="text-caption text-on-surface-variant">Saldo: S/ {formatMoney(wallet.balance)}</p>
          </div>
          {wallet.is_primary ? (
            <div aria-disabled="true" className="flex w-full items-center gap-3 rounded-2xl p-3 opacity-60">
              <span className="flex h-10 w-10 items-center justify-center rounded-full bg-surface-container-high"><Icon name="lock" className="text-[20px]" /></span>
              <span><span className="block text-[15px] font-bold">Eliminar billetera</span>
                <span className="block text-caption text-on-surface-variant">Es tu billetera oficial vinculada a tu DNI: no se puede eliminar.</span></span>
            </div>
          ) : (
            <button type="button" onClick={() => setView("delete")} className="flex w-full items-center gap-3 rounded-2xl p-3 text-left hover:bg-error-container/40">
              <span className="flex h-10 w-10 items-center justify-center rounded-full bg-error-container text-error"><Icon name="delete" className="text-[20px]" /></span>
              <span className="flex-1"><span className="block text-[15px] font-bold text-error">Eliminar billetera</span>
                <span className="block text-caption text-on-surface-variant">{hasMoney ? "Primero moverás su saldo a otra billetera" : "Se borrará junto con sus movimientos"}</span></span>
              <Icon name="chevron_right" className="text-[20px] text-outline" />
            </button>
          )}
        </>
      ) : (
        <div>
          <span className="mb-2 flex h-12 w-12 items-center justify-center rounded-full bg-error-container text-error">
            <Icon name={hasMoney ? "account_balance_wallet" : "delete"} className="text-[26px]" />
          </span>
          <h2 className="text-title">{hasMoney ? `${wallet.name} tiene S/ ${formatMoney(wallet.balance)}` : `¿Eliminar ${wallet.name}?`}</h2>
          <p className="mt-1 text-sm text-on-surface-variant">
            {hasMoney ? "Para eliminarla, primero elige a qué billetera mover tu dinero." : "La billetera dejará de aparecer en tu inicio y su QR dejará de funcionar."}
          </p>
          {hasMoney && (
            <div className="mt-4">
              <WalletSelect label="Mover el saldo a" options={others} value={destination}
                onChange={(id) => { setDestination(id); setError(null); }} hint={() => `Recibirá S/ ${formatMoney(wallet.balance)}`} />
            </div>
          )}
          <div className="mt-4 flex items-start gap-2 rounded-xl bg-error-container/50 p-3">
            <Icon name="warning" className="text-[20px] text-error" />
            <p className="text-caption text-on-error-container">También se eliminarán sus movimientos. Esta acción no se puede deshacer.</p>
          </div>
          {error && <p role="alert" className="mt-2 text-sm text-error">{error}</p>}
          <div className="mt-4 flex gap-2">
            <button type="button" onClick={close} className="h-12 flex-1 rounded-xl border-2 border-outline-variant text-label text-on-surface-variant">Cancelar</button>
            <button type="button" onClick={confirm} disabled={archive.isPending} className="h-12 flex-1 rounded-xl bg-error text-label text-on-error disabled:opacity-60">
              {hasMoney ? "Mover y eliminar" : "Eliminar"}
            </button>
          </div>
        </div>
      )}
    </BottomSheet>
  );
}
