/** Lógica pura del yapeo: teclado, límites y categorías. Probada con Vitest. */
import type { Category, Wallet } from "@/lib/api/types";

export const PER_PAYMENT_LIMIT = 500;
export const DAILY_LIMIT = 2000;
export const MESSAGE_MAX = 40;

export type Key = "0" | "1" | "2" | "3" | "4" | "5" | "6" | "7" | "8" | "9" | "." | "backspace";

/** Aplica una tecla al monto: máx. 4 enteros y 2 decimales, sin ceros a la izquierda. */
export function pressKey(current: string, key: Key): string {
  if (key === "backspace") return current.slice(0, -1) || "0";
  if (key === ".") return current.includes(".") ? current : `${current}.`;
  const [integer, decimals] = current.split(".");
  if (decimals !== undefined) return decimals.length < 2 ? current + key : current;
  if (current === "0") return key;
  return integer.length < 4 ? current + key : current;
}

/** Validación inmediata en el cliente; el backend vuelve a validar (fuente de verdad). */
export function amountError(amount: number, balance: number): string | null {
  if (!(amount > 0)) return "Ingresa un monto mayor a S/ 0";
  if (amount > PER_PAYMENT_LIMIT) return `Límite por yapeo: S/ ${PER_PAYMENT_LIMIT}`;
  if (amount > balance) return `Saldo insuficiente. Disponible: S/ ${balance.toFixed(2)}`;
  return null;
}

export const CATEGORIES: { code: Category; emoji: string; label: string }[] = [
  { code: "RESTOCK", emoji: "📦", label: "Para volver a surtir" },
  { code: "LOCAL_SERVICES", emoji: "💡", label: "Para pagar local/servicios/ayudantes" },
  { code: "FAMILY", emoji: "👨‍👩‍👧", label: "Para mí o mi familia" },
];

/** Las categorías solo aplican a billeteras de negocio (regla del backend). */
export const allowsCategories = (wallet?: Pick<Wallet, "is_business"> | null) => Boolean(wallet?.is_business);

export type Contact = { name: string; phone: string };
export const CONTACTS: Contact[] = [
  { name: "Lucía Góm*", phone: "987 654 321" },
  { name: "Carlos Rui*", phone: "912 345 678" },
  { name: "Susan Mar*", phone: "987 112 445" },
  { name: "Proveedor Café", phone: "998 877 665" },
];
export const DEMO_RECIPIENTS = [
  { name: "BoticaPeru", type: "MERCHANT" },
  { name: "Restaurante Mary", type: "MERCHANT" },
  { name: "Susan Mar*", type: "CONTACT" },
  { name: "Makro", type: "MERCHANT" },
  { name: "Stephen Cuo*", type: "CONTACT" },
] as const;

let recipientIndex = 0;

/** Avanza solo al iniciar un pago o detectar un QR, nunca al cambiar el monto. */
export function nextDemoRecipient() {
  let index = recipientIndex;
  try {
    const stored = Number(window.sessionStorage.getItem("mica-recipient-index") ?? "0");
    if (Number.isSafeInteger(stored) && stored >= 0) index = stored;
  } catch {
    // La rotación funciona también sin almacenamiento disponible.
  }
  const recipient = DEMO_RECIPIENTS[index % DEMO_RECIPIENTS.length];
  recipientIndex = (index + 1) % DEMO_RECIPIENTS.length;
  try {
    window.sessionStorage.setItem("mica-recipient-index", String(recipientIndex));
  } catch {
    // Conserva el índice en memoria.
  }
  return recipient;
}
