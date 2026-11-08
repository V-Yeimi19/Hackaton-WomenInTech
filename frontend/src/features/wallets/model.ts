/** Reglas de presentación de billeteras (puras). */
import type { Wallet } from "@/lib/api/types";

export const WALLET_ICON: Record<Wallet["role"], string> = {
  PRINCIPAL: "account_balance_wallet",
  BUSINESS: "storefront",
  SAVINGS: "savings",
  CUSTOM: "shopping_bag",
};

export function walletTag(wallet: Wallet): string {
  if (wallet.role === "PRINCIPAL") return "DNI / Celular Oficial";
  if (wallet.role === "BUSINESS") return "Negocio / Ventas";
  if (wallet.role === "SAVINGS") return "Ahorro";
  return wallet.purpose === "SAVINGS" ? "Ahorro" : "Negocio";
}

/** El ícono elegido al crear (emoji) tiene prioridad sobre el ícono por rol. */
export const isEmoji = (icon?: string | null) => Boolean(icon && !/^[a-z_]+$/.test(icon));

export const NAME_MIN = 3;
export const NAME_MAX = 24;

/** Validación de nombre igual que el backend, para responder sin esperar a la red. */
export function nameError(raw: string, existing: Wallet[]): string | null {
  const name = raw.replace(/\s+/g, " ").trim();
  if (!name) return "Escribe un nombre para tu billetera.";
  if (name.length < NAME_MIN) return "El nombre debe tener al menos 3 caracteres.";
  if (name.length > NAME_MAX) return "Máximo 24 caracteres.";
  if (existing.some((w) => w.name.toLowerCase() === name.toLowerCase())) return "Ya tienes una billetera con ese nombre.";
  return null;
}
