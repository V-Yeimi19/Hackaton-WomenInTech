"use client";

import Image from "next/image";
import Link from "next/link";
import { useState, type ReactNode } from "react";

import { Icon } from "@/components/ui/Icon";
import { useToast } from "@/components/ui/Toast";
import { useTransfer, useWallets } from "@/features/wallets/api";
import { formatMoney } from "@/lib/format";

import { useWalletHistory } from "./api";
import { averageDailySales, savingsSplit } from "./summary";

const RATE = 0.3;

/** Respuesta de Mica con la tarjeta "Sugerencia de ahorro": separa parte del saldo del negocio hacia Ahorro. */
export function SavingsSuggestion({ walletId }: { walletId: string }) {
  const toast = useToast();
  const wallets = useWallets();
  const history = useWalletHistory(walletId);
  const transfer = useTransfer();
  const [done, setDone] = useState<{ save: string; target: string } | null>(null);
  const [error, setError] = useState("");

  const items = wallets.data?.items ?? [];
  const source = items.find((w) => w.id === walletId);
  const savings = items.find((w) => w.id !== walletId && (w.role === "SAVINGS" || w.purpose === "SAVINGS"));
  const split = source ? savingsSplit(source.balance, RATE) : null;

  async function send() {
    if (!split || !savings || transfer.isPending) return;
    setError("");
    try {
      await transfer.mutateAsync({ from_wallet_id: walletId, to_wallet_id: savings.id, amount: split.save, note: "Ahorro sugerido por Mica" });
      setDone({ save: split.save, target: savings.name });
      toast(`S/ ${formatMoney(split.save)} transferidos a ${savings.name}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No pude hacer la transferencia. Intenta de nuevo.");
    }
  }

  const bubble = (content: ReactNode) => (
    <div className="flex items-end gap-2">
      <Image src="/mica-avatar.jpg" alt="Mica" width={30} height={30} className="h-[30px] w-[30px] shrink-0 rounded-full object-cover" />
      <div className="max-w-[85%] rounded-2xl bg-white px-4 py-3 text-sm leading-6">{content}</div>
    </div>
  );

  if (wallets.isPending || history.isPending) return bubble(<p role="status">Estoy calculando cuánto puedes apartar…</p>);
  if (wallets.isError || history.isError || !source) return bubble(<p>No pude revisar tu saldo en este momento. Intenta de nuevo en unos segundos.</p>);

  const average = averageDailySales(history.data, walletId);
  const intro = Number(average) > 0
    ? <>Basado en tus ventas promedio de esta semana (aprox. <strong className="text-primary">S/ {formatMoney(average)}</strong> al día):</>
    : <>Aún no veo ventas esta semana, pero según tu saldo actual en {source.name} (<strong className="text-primary">S/ {formatMoney(source.balance)}</strong>):</>;

  if (!done && !split) return bubble(<p>Por ahora no tienes saldo suficiente en {source.name} para separar. Cuando recibas más cobros, te ayudo a apartar una parte. 💜</p>);

  const shown = done ? { save: done.save, keep: null } : split!;
  return (
    <div className="space-y-2">
      {bubble(<>
        <p>{intro}</p>
        <p className="mt-2">Te recomiendo apartar un <strong className="rounded bg-secondary-fixed/60 px-1">{RATE * 100}% (S/ {formatMoney(shown.save)})</strong> en tu billetera de Ahorro. Si quieres, ¡lo transfiero ahora mismo! ✨</p>
      </>)}
      <section aria-label="Sugerencia de ahorro" className="ml-10 rounded-[24px] bg-surface-container-low p-4">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-secondary-fixed text-on-secondary-fixed-variant"><Icon name="savings" size={22} /></span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-bold text-primary">Sugerencia de ahorro</p>
            <p className="text-xs font-semibold leading-4 text-on-surface-variant">Protege tu flujo de caja</p>
          </div>
          <span className="shrink-0 rounded-full bg-secondary-container px-2.5 py-1 text-[11px] font-bold text-on-secondary-container">Recomendado</span>
        </div>
        <div className="mt-3 grid grid-cols-2 rounded-2xl bg-white p-3">
          <div><p className="text-xs text-on-surface-variant">A separar hoy</p><p className="text-lg font-bold text-primary">S/ {formatMoney(shown.save)}</p></div>
          {shown.keep && <div className="border-l border-outline-variant/50 pl-3"><p className="text-xs text-on-surface-variant">Para mercadería</p><p className="text-lg font-bold text-secondary">S/ {formatMoney(shown.keep)}</p></div>}
        </div>
        {done ? (
          <p role="status" className="mt-3 flex h-12 items-center justify-center gap-2 rounded-full bg-secondary-container text-sm font-bold text-on-secondary-container">
            <Icon name="check_circle" size={20} />Transferido a {done.target}
          </p>
        ) : savings ? (
          <button type="button" onClick={send} disabled={transfer.isPending}
            className="mt-3 flex h-12 w-full items-center justify-center gap-2 rounded-full bg-primary-container text-sm font-bold text-white disabled:opacity-60">
            <Icon name="arrow_forward" size={20} />{transfer.isPending ? "Transfiriendo…" : `Transferir S/ ${formatMoney(split!.save)} a ${savings.name}`}
          </button>
        ) : (
          <Link href="/billeteras/nueva" className="mt-3 flex h-12 w-full items-center justify-center gap-2 rounded-full bg-primary-container text-sm font-bold text-white">
            <Icon name="add" size={20} />Crear billetera de Ahorro
          </Link>
        )}
        {error && <p role="alert" className="mt-2 text-sm text-error">{error}</p>}
      </section>
    </div>
  );
}
