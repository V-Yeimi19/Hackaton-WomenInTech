/** Reglas de presentación de billeteras (puras). */
import type { Wallet } from "@/lib/api/types";

export const WALLET_COLORS = {
  purple: { label: "Violeta", dot: "bg-[#8b5ac7]", card: "from-[#8b5ac7] to-[#7041ad]", corner: "bg-[#8b5ac7]/20" },
  teal: { label: "Turquesa", dot: "bg-[#168578]", card: "from-[#168578] to-[#09695f]", corner: "bg-[#168578]/20" },
  magenta: { label: "Coral", dot: "bg-[#c75560]", card: "from-[#c75560] to-[#ae3d50]", corner: "bg-[#c75560]/20" },
  night: { label: "Azul cielo", dot: "bg-[#4279c7]", card: "from-[#4279c7] to-[#2e5fa7]", corner: "bg-[#4279c7]/20" },
} as const;

export const WALLET_ICON: Record<Wallet["role"], string> = {
  PRINCIPAL: "account_balance_wallet",
  BUSINESS: "storefront",
  SAVINGS: "savings",
  CUSTOM: "shopping_bag",
};

export function walletTag(wallet: Wallet): string {
  if (wallet.role === "PRINCIPAL") return "DNI / Celular Oficial";
  if (wallet.role === "BUSINESS") return "Negocio";
  if (wallet.role === "SAVINGS") return "Ahorro";
  return wallet.purpose === "SAVINGS" ? "Ahorro" : "Negocio";
}

/** El ícono elegido al crear (emoji) tiene prioridad sobre el ícono por rol. */
export const isEmoji = (icon?: string | null) => Boolean(icon && !/^[a-z_]+$/.test(icon));

export const NAME_MIN = 3;
export const NAME_MAX = 24;

export function normalizeWalletName(raw: string): string {
  const name = raw.normalize("NFC").replace(/\s+/g, " ").trim();
  return name.charAt(0).toLocaleUpperCase("es-PE") + name.slice(1);
}

export function walletNameInput(raw: string): string {
  const letters = raw.normalize("NFC").replace(/[^\p{L} ]/gu, "");
  return letters.charAt(0).toLocaleUpperCase("es-PE") + letters.slice(1);
}

/** Validación de nombre igual que el backend, para responder sin esperar a la red. */
export function nameError(raw: string, existing: Wallet[]): string | null {
  const name = normalizeWalletName(raw);
  if (!name) return "Escribe un nombre para tu billetera.";
  if (!/^[\p{L} ]+$/u.test(name)) return "Usa solo letras y espacios.";
  if (name.length < NAME_MIN) return "El nombre debe tener al menos 3 caracteres.";
  if (name.length > NAME_MAX) return "Máximo 24 caracteres.";
  if (existing.some((w) => w.name.toLowerCase() === name.toLowerCase())) return "Ya tienes una billetera con ese nombre.";
  return null;
}
