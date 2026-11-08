/** Claves de caché centralizadas: una sola fuente para leer e invalidar. */
export const queryKeys = {
  wallets: ["wallets"] as const,
  movements: (walletId?: string) => ["movements", walletId ?? "all"] as const,
  movementsAll: ["movements"] as const,
  movement: (id: string) => ["movement", id] as const,
  me: ["me"] as const,
  telegramLink: ["telegram-link"] as const,
};
