"use client";

import { useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useToast } from "@/components/ui/Toast";
import { queryKeys } from "@/lib/api/query-keys";
import type { Wallet } from "@/lib/api/types";
import { getProfile } from "@/features/mica/api";
import { dailySalesCents, demoPayments } from "./demo-payments";

type Batch = { payments: ReturnType<typeof demoPayments>; keys: string[]; done: number };

/** Índice de "En un día normal, ¿más o menos cuánto vendes?" en el perfil de Mica. */
const DAILY_SALES_ANSWER = 2;
/** Venta diaria de referencia (S/ 300) mientras Mica aún no conoce la de la billetera. */
export const DEFAULT_DAILY_SALES_CENTS = 30_000;

/**
 * Ventas diarias declaradas a Mica. El perfil vive en el servidor (agent/profile);
 * sessionStorage solo queda como respaldo de perfiles anteriores aún no migrados.
 */
async function declaredDailySales(walletId: string): Promise<string> {
  const profile = await getProfile(walletId);
  const saved = profile.answers[DAILY_SALES_ANSWER];
  if (typeof saved === "string") return saved;
  try {
    const legacy: unknown = JSON.parse(sessionStorage.getItem(`mica-onboarding:${walletId}`) ?? "[]");
    if (Array.isArray(legacy) && typeof legacy[DAILY_SALES_ANSWER] === "string") return legacy[DAILY_SALES_ANSWER];
  } catch { /* Sin datos locales. */ }
  return "";
}

/**
 * Cada toque del ícono pide 10 yapeos recibidos que suman las ventas diarias que
 * Mica conoce (o S/ 300 de referencia si aún no las conoce). Los toques se encolan: tres toques seguidos generan 30 yapeos, uno
 * tras otro. Si la red falla a mitad de una tanda, el siguiente toque la completa
 * con las mismas claves de idempotencia (sin duplicar cobros).
 */
export function useDemoYapeos() {
  const client = useQueryClient();
  const toast = useToast();
  const queue = useRef<Wallet[]>([]);
  const running = useRef(false);
  const [generating, setGenerating] = useState(false);
  const batches = useRef(new Map<string, Batch>());

  async function prepare(wallet: Wallet): Promise<Batch> {
    const pending = batches.current.get(wallet.id);
    if (pending) return pending;
    // Siempre genera: si Mica aún no sabe cuánto vende (o no se pudo leer el
    // perfil), usa la venta diaria de referencia.
    const average = await declaredDailySales(wallet.id).catch(() => "");
    const total = dailySalesCents(average) ?? DEFAULT_DAILY_SALES_CENTS;
    const payments = demoPayments(total);
    const batch = { payments, keys: payments.map(() => crypto.randomUUID()), done: 0 };
    batches.current.set(wallet.id, batch);
    return batch;
  }

  async function refresh() {
    await Promise.all([
      client.invalidateQueries({ queryKey: queryKeys.wallets }),
      client.invalidateQueries({ queryKey: queryKeys.movementsAll }),
      client.invalidateQueries({ queryKey: ["mica", "history"] }),
    ]).catch(() => undefined);
  }

  async function run() {
    running.current = true;
    setGenerating(true);
    try {
      while (queue.current.length > 0) {
        const wallet = queue.current[0];
        const batch = await prepare(wallet);
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
        } catch {
          queue.current = [];
          toast("No se completaron los yapeos. Pulsa el ícono para reintentar los pendientes.");
          break;
        }
        batches.current.delete(wallet.id);
        queue.current.shift();
        await refresh();
      }
    } finally {
      await refresh();
      running.current = false;
      setGenerating(false);
    }
  }

  function generate(wallet: Wallet) {
    queue.current.push(wallet);
    if (!running.current) void run();
  }

  return { generate, generating };
}
