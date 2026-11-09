"use client";

import { useEffect, useRef } from "react";
import { formatMoney } from "@/lib/format";
import { useWalletHistory } from "./api";
import { summarizeToday } from "./summary";

export function MovementSummary({ walletId, walletName }: { walletId: string; walletName: string }) {
  const message = useRef<HTMLDivElement>(null);
  const history = useWalletHistory(walletId);

  useEffect(() => {
    if (!history.isFetching && history.isSuccess) {
      message.current?.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [history.isFetching, history.isSuccess, history.dataUpdatedAt]);

  if (history.isPending || history.isFetching) return <p role="status">Estoy revisando los movimientos de tu billetera <strong>“{walletName}”</strong>…</p>;
  if (history.isError) return <p>No pude consultar tus movimientos en este momento. <button type="button" onClick={() => history.refetch()} className="font-bold text-secondary underline">Reintentar</button></p>;

  const totals = summarizeToday(history.data, walletId);
  return <div ref={message}><p>¡Hola! Soy <strong>Mica</strong>, tu asesora de Yape. He estado revisando los movimientos de tu billetera <strong>“{walletName}”</strong>. Hoy llevas <strong>S/ {formatMoney(totals.collected)}</strong> en cobros registrados y <strong>S/ {formatMoney(totals.transferred)}</strong> transferidos a tu billetera principal.</p><p className="mt-2 font-semibold text-primary">¿En qué te puedo apoyarte hoy para hacer crecer tu negocio?</p></div>;
}
