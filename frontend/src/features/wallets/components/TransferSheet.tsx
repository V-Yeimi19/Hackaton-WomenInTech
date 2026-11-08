"use client";

import { useState } from "react";

import { BottomSheet } from "@/components/ui/BottomSheet";
import { Icon } from "@/components/ui/Icon";
import { useToast } from "@/components/ui/Toast";
import type { Wallet } from "@/lib/api/types";
import { formatMoney } from "@/lib/format";

import { useTransfer } from "../api";
import { WalletSelect } from "./WalletSelect";

const NOTE_MAX = 40;

/** Transferir entre billeteras, con descripción opcional. El backend valida saldo y montos. */
export function TransferSheet({ open, onClose, wallets }: { open: boolean; onClose: () => void; wallets: Wallet[] }) {
  const toast = useToast();
  const transfer = useTransfer();
  const [from, setFrom] = useState<string | null>(null);
  const [to, setTo] = useState<string | null>(null);
  const [amount, setAmount] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);

  const source = wallets.find((w) => w.id === from);
  const value = Number(amount.replace(",", "."));

  function reset() {
    setFrom(null); setTo(null); setAmount(""); setNote(""); setError(null);
    onClose();
  }

  async function send() {
    if (!from) return setError("Elige la billetera de origen.");
    if (!to) return setError("Elige la billetera de destino.");
    if (!(value > 0)) return setError("Ingresa un monto mayor a S/ 0.");
    try {
      await transfer.mutateAsync({ from_wallet_id: from, to_wallet_id: to, amount: value.toFixed(2), note: note.trim() || null });
      const target = wallets.find((w) => w.id === to)?.name;
      reset();
      toast(`S/ ${formatMoney(value)} transferidos a ${target}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No pudimos transferir.");
    }
  }

  return (
    <BottomSheet open={open} onClose={reset} eyebrow="Entre mis billeteras" title="Transferir" subtitle="Al instante y sin comisiones.">
      <div className="flex flex-col gap-1">
        <WalletSelect label="Desde" options={wallets} value={from} disableEmpty
          onChange={(id) => { setFrom(id); if (id === to) setTo(null); setError(null); }} />
        <div className="relative z-10 -my-1 flex justify-center">
          <button type="button" aria-label="Intercambiar origen y destino"
            onClick={() => { setFrom(to); setTo(from); setError(null); }}
            className="mt-2 flex h-9 w-9 items-center justify-center rounded-full bg-surface-container-high text-primary-container hover:bg-primary-fixed">
            <Icon name="swap_vert" className="text-[20px]" />
          </button>
        </div>
        <WalletSelect label="Hacia" options={wallets.filter((w) => w.id !== from)} value={to} onChange={(id) => { setTo(id); setError(null); }} />
      </div>

      <p className="mb-2 mt-4 text-caption font-bold uppercase tracking-wider text-on-surface-variant">Monto</p>
      <div className="flex items-center gap-2 rounded-xl border-2 border-outline-variant bg-surface px-3 focus-within:border-primary-container">
        <span className="text-title font-bold text-primary-container">S/</span>
        <input aria-label="Monto" inputMode="decimal" placeholder="0.00" value={amount}
          onChange={(e) => { setAmount(e.target.value); setError(null); }} className="h-12 flex-1 bg-transparent text-title outline-none" />
        <button type="button" onClick={() => source && setAmount(Number(source.balance).toFixed(2))}
          className="rounded-full bg-secondary-container/60 px-3 py-1 text-caption font-bold text-on-secondary-container">Todo</button>
      </div>
      <p className="mt-1.5 text-caption text-on-surface-variant">{source ? `Disponible: S/ ${formatMoney(source.balance)}` : "Elige la billetera de origen"}</p>

      <div className="mb-2 mt-4 flex items-center justify-between">
        <p className="text-caption font-bold uppercase tracking-wider text-on-surface-variant">
          Descripción <span className="font-normal normal-case tracking-normal">(opcional)</span>
        </p>
        <span className="text-caption text-on-surface-variant">{note.length}/{NOTE_MAX}</span>
      </div>
      <label className="flex items-center gap-2 rounded-xl border-2 border-outline-variant bg-surface px-3 focus-within:border-primary-container">
        <Icon name="edit_note" className="text-[20px] text-on-surface-variant" />
        <input aria-label="Descripción" maxLength={NOTE_MAX} placeholder="Ej.: Para comprar mercadería" value={note}
          onChange={(e) => setNote(e.target.value)} className="h-12 flex-1 bg-transparent outline-none" />
      </label>

      {error && <p role="alert" className="mt-2 text-sm text-error">{error}</p>}
      <button type="button" onClick={send} disabled={transfer.isPending}
        className="mt-4 flex h-12 w-full items-center justify-center gap-2 rounded-xl bg-secondary text-label text-on-secondary disabled:opacity-60">
        <Icon name="swap_horiz" className="text-[20px]" />
        {value > 0 ? `Transferir S/ ${formatMoney(value)}` : "Transferir"}
      </button>
    </BottomSheet>
  );
}
