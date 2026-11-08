"use client";

import Image from "next/image";
import Link from "next/link";

import { Icon } from "@/components/ui/Icon";
import { useToast } from "@/components/ui/Toast";

/** Barra inferior (Escanear QR / Yapear) y acceso al agente Mica, solo en Inicio. */
export function BottomBar({ onYapear, hideAgent }: { onYapear: () => void; hideAgent: boolean }) {
  const toast = useToast();
  return (
    <>
      {!hideAgent && (
        <button type="button" aria-label="Hablar con Mica, tu asesora contable"
          onClick={() => toast("Pronto podrás hablar con Mica, tu asesora contable")}
          className="fixed bottom-[104px] right-[max(1rem,calc(50%-215px+1rem))] z-50 h-16 w-16 overflow-hidden rounded-full bg-white shadow-[0_8px_24px_rgba(89,0,106,0.35)] ring-4 ring-surface transition-transform hover:scale-105 active:scale-95">
          <Image src="/mica-avatar.jpg" alt="" width={64} height={64} className="h-full w-full object-cover" />
        </button>
      )}
      <nav className="fixed bottom-0 left-1/2 z-50 w-full max-w-[430px] -translate-x-1/2 bg-surface/95 shadow-[0_-4px_24px_rgba(116,34,132,0.08)] backdrop-blur-xl">
        <div className="flex gap-2 px-4 py-3">
          <Link href="/escanear" className="flex h-12 flex-1 items-center justify-center gap-2 rounded-xl border-2 border-secondary bg-surface-container-lowest text-label uppercase tracking-wide text-secondary">
            <Icon name="qr_code_scanner" className="text-[22px]" />
            Escanear QR
          </Link>
          <button type="button" onClick={onYapear} className="flex h-12 flex-1 items-center justify-center gap-2 rounded-xl bg-secondary text-label uppercase tracking-wide text-on-secondary shadow-sm">
            <Icon name="send" className="text-[22px]" />
            Yapear
          </button>
        </div>
      </nav>
    </>
  );
}
