import type { Movement } from "@/lib/api/types";

const limaDay = new Intl.DateTimeFormat("en-CA", { timeZone: "America/Lima", year: "numeric", month: "2-digit", day: "2-digit" });

function cents(amount: string): number {
  const [whole, fraction = ""] = amount.replace(/^-/, "").split(".");
  return Number(whole) * 100 + Number(fraction.padEnd(2, "0"));
}

const DAY_MS = 24 * 60 * 60 * 1000;

/** Promedio diario de cobros (ventas) de la billetera en los últimos `days` días. */
export function averageDailySales(movements: Movement[], walletId: string, now = new Date(), days = 7): string {
  const since = now.getTime() - days * DAY_MS;
  let total = 0;
  for (const movement of movements) {
    if (new Date(movement.occurred_at).getTime() < since) continue;
    const leg = movement.wallets.find((wallet) => wallet.id === walletId);
    if (leg && movement.kind === "SALE" && Number(leg.delta) > 0) total += cents(leg.delta);
  }
  return (Math.round(total / days) / 100).toFixed(2);
}

/** Parte del saldo a separar (redondeada a soles enteros) y lo que queda para mercadería. */
export function savingsSplit(balance: string, rate = 0.3): { save: string; keep: string } | null {
  const total = cents(balance);
  const save = Math.floor((total * rate) / 100) * 100;
  if (save <= 0) return null;
  return { save: (save / 100).toFixed(2), keep: ((total - save) / 100).toFixed(2) };
}

export function summarizeToday(movements: Movement[], walletId: string, now = new Date()) {
  let collected = 0;
  let transferred = 0;
  const today = limaDay.format(now);
  for (const movement of movements) {
    if (limaDay.format(new Date(movement.occurred_at)) !== today) continue;
    const leg = movement.wallets.find((wallet) => wallet.id === walletId);
    if (!leg) continue;
    if (movement.kind === "SALE" && Number(leg.delta) > 0) collected += cents(leg.delta);
    if (movement.direction === "TRANSFER" && movement.from_wallet?.id === walletId
      && movement.wallets.some((wallet) => wallet.role === "PRINCIPAL" && Number(wallet.delta) > 0)) {
      transferred += cents(leg.delta);
    }
  }
  return { collected: (collected / 100).toFixed(2), transferred: (transferred / 100).toFixed(2) };
}
