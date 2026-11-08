"use client";

import { useEffect } from "react";

import { Icon } from "@/components/ui/Icon";

import type { Key } from "./model";

const KEYS: { key: Key; sub?: string }[] = [
  { key: "1" }, { key: "2", sub: "ABC" }, { key: "3", sub: "DEF" },
  { key: "4", sub: "GHI" }, { key: "5", sub: "JKL" }, { key: "6", sub: "MNO" },
  { key: "7", sub: "PQRS" }, { key: "8", sub: "TUV" }, { key: "9", sub: "WXYZ" },
  { key: "." }, { key: "0" }, { key: "backspace" },
];

/** Teclado numérico de la pantalla de monto; también acepta el teclado físico. */
export function Keypad({ onKey, onEnter }: { onKey: (key: Key) => void; onEnter: () => void }) {
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.target as HTMLElement).tagName === "INPUT") return;
      if (/^[0-9]$/.test(event.key)) onKey(event.key as Key);
      else if (event.key === "." || event.key === ",") onKey(".");
      else if (event.key === "Backspace") onKey("backspace");
      else if (event.key === "Enter") onEnter();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onKey, onEnter]);

  return (
    <div className="grid grid-cols-3 gap-1.5 bg-surface-container-high p-2">
      {KEYS.map(({ key, sub }) => (
        <button key={key} type="button" data-key={key} onClick={() => onKey(key)}
          aria-label={key === "backspace" ? "Borrar" : key === "." ? "Punto decimal" : key}
          className="flex h-12 flex-col items-center justify-center rounded-xl bg-surface-container-lowest shadow-[0_1px_2px_rgba(0,0,0,0.1)] active:bg-surface-container-highest">
          {key === "backspace" ? <Icon name="backspace" className="text-[22px]" /> : <span className="text-[22px] font-semibold leading-6">{key}</span>}
          {sub && <span className="text-[9px] font-bold tracking-wider text-on-surface-variant">{sub}</span>}
        </button>
      ))}
    </div>
  );
}
