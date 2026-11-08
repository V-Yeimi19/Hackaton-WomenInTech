"use client";

import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";

const ToastContext = createContext<(message: string) => void>(() => {});

/** Avisos breves (equivalente al toast del prototipo), anunciados a lectores de pantalla. */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [message, setMessage] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);

  const show = useCallback((text: string) => {
    setMessage(text);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setMessage(null), 2400);
  }, []);

  return (
    <ToastContext.Provider value={show}>
      {children}
      <div
        role="status"
        aria-live="polite"
        className={`pointer-events-none fixed left-1/2 top-20 z-[90] max-w-[85%] -translate-x-1/2 rounded-2xl bg-inverse-surface px-4 py-2.5 text-center text-sm font-bold text-white transition-all duration-200 ${message ? "opacity-100" : "-translate-y-2 opacity-0"}`}
      >
        {message}
      </div>
    </ToastContext.Provider>
  );
}

export const useToast = () => useContext(ToastContext);
