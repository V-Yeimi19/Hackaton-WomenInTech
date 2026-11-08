"use client";

import { useStoredState } from "@/lib/use-session-storage";

export function resetBalanceVisibility() {
  try {
    window.sessionStorage.removeItem("mica-shown-wallets");
    window.sessionStorage.removeItem("mica-total-shown");
  } catch {
    // Sin almacenamiento, los saldos ya están ocultos por defecto.
  }
}

/** Saldos ocultos por defecto; el ojito de cada billetera los muestra durante la sesión. */
export function useBalanceVisibility() {
  const [shown, setShown] = useStoredState<string[]>("mica-shown-wallets", []);
  const [totalShown, setTotalShown] = useStoredState<boolean>("mica-total-shown", false);
  return {
    isShown: (walletId: string) => shown.includes(walletId),
    toggle: (walletId: string) =>
      setShown((ids) => (ids.includes(walletId) ? ids.filter((id) => id !== walletId) : [...ids, walletId])),
    totalShown,
    toggleTotal: () => setTotalShown((value) => !value),
  };
}
