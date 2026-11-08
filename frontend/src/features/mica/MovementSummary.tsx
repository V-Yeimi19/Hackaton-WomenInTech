"use client";

import { useEffect, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { backend } from "@/lib/api/http";
import type { Movement, MovementList } from "@/lib/api/types";
import { formatMoney } from "@/lib/format";
import { summarizeToday } from "./summary";

export function MovementSummary({ walletId, walletName }: { walletId: string; walletName: string }) {
  const message = useRef<HTMLDivElement>(null);
  const history = useQuery({
    queryKey: ["mica", "history", walletId],
    queryFn: async () => {
      const movements: Movement[] = [];
      let cursor: string | null | undefined;
      do {
        const params = new URLSearchParams({ wallet_id: walletId, limit: "100" });
        if (cursor) params.set("cursor", cursor);
        const page = await backend<MovementList>(`movements?${params}`);
        movements.push(...page.items);
        cursor = page.next_cursor;
      } while (cursor);
      return movements;
    },
    staleTime: 0,
    refetchOnMount: "always",
  });

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
