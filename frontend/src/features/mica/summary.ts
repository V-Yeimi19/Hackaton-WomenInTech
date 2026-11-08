import type { Movement } from "@/lib/api/types";

const limaDay = new Intl.DateTimeFormat("en-CA", { timeZone: "America/Lima", year: "numeric", month: "2-digit", day: "2-digit" });

function cents(amount: string): number {
  const [whole, fraction = ""] = amount.replace(/^-/, "").split(".");
  return Number(whole) * 100 + Number(fraction.padEnd(2, "0"));
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
