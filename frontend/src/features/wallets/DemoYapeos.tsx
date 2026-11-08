"use client";

import { useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useToast } from "@/components/ui/Toast";
import { queryKeys } from "@/lib/api/query-keys";
import type { Wallet } from "@/lib/api/types";
import { dailySalesCents, demoPayments } from "./demo-payments";

type Batch = { payments: ReturnType<typeof demoPayments>; keys: string[]; done: number };

/** El ícono genera los cobros directamente; los reintentos conservan sus claves. */
export function useDemoYapeos() {
  const client = useQueryClient();
  const toast = useToast();
  const busy = useRef(false);
  const [generating, setGenerating] = useState(false);
  const batches = useRef(new Map<string, Batch>());

  async function generate(wallet: Wallet) {
    if (busy.current) return;
    let batch = batches.current.get(wallet.id);
    if (!batch) {
      let average = "";
      try {
        const answers: unknown = JSON.parse(sessionStorage.getItem(`mica-onboarding:${wallet.id}`) ?? "[]");
        if (Array.isArray(answers) && typeof answers[2] === "string") average = answers[2];
      } catch { /* Sin perfil válido no se generan cobros. */ }
      const total = dailySalesCents(average);
      if (total === null) {
        toast("Primero registra tus ventas diarias con Mica para esta billetera.");
        return;
      }
      const payments = demoPayments(total);
      batch = { payments, keys: payments.map(() => crypto.randomUUID()), done: 0 };
      batches.current.set(wallet.id, batch);
    }
    busy.current = true;
    setGenerating(true);
    try {
      while (batch.done < batch.payments.length) {
        const index = batch.done;
        const { name, amount } = batch.payments[index];
        const response = await fetch("/api/backend/demo/incoming-yapes", {
          method: "POST",
          headers: { "content-type": "application/json", "Idempotency-Key": batch.keys[index] },
          body: JSON.stringify({ to_wallet_id: wallet.id, amount, from_name: `${name} (demo)` }),
        });
        if (!response.ok) throw new Error("No se pudo recibir el yapeo de prueba.");
        batch.done += 1;
      }
      batches.current.delete(wallet.id);
    } catch {
      toast("No se completaron los yapeos. Pulsa el ícono para reintentar los pendientes.");
    } finally {
      try {
        await Promise.all([
          client.invalidateQueries({ queryKey: queryKeys.wallets }),
          client.invalidateQueries({ queryKey: queryKeys.movementsAll }),
          client.invalidateQueries({ queryKey: ["mica", "history"] }),
        ]);
      } finally {
        busy.current = false;
        setGenerating(false);
      }
    }
  }

  return { generate, generating };
}
