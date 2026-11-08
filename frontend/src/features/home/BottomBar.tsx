"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useRef, useState, type PointerEvent } from "react";

import { Icon } from "@/components/ui/Icon";
import { useToast } from "@/components/ui/Toast";

/** Barra inferior (Escanear QR / Yapear) y acceso al agente Mica, solo en Inicio. */
export function BottomBar({ onYapear, hideAgent }: { onYapear: () => void; hideAgent: boolean }) {
  const toast = useToast();
  const [agentBottom, setAgentBottom] = useState(104);
  const drag = useRef<{ pointerId: number; startY: number; startBottom: number; moved: boolean } | null>(null);
  const suppressClick = useRef(false);

  function clampBottom(bottom: number) {
    return Math.max(92, Math.min(bottom, Math.max(92, window.innerHeight - 80)));
  }

  useEffect(() => {
    const resize = () => setAgentBottom((bottom) => clampBottom(bottom));
    resize();
    window.addEventListener("resize", resize);
    return () => window.removeEventListener("resize", resize);
  }, []);

  function startDrag(event: PointerEvent<HTMLButtonElement>) {
    if (!event.isPrimary || event.button !== 0) return;
    suppressClick.current = false;
    drag.current = { pointerId: event.pointerId, startY: event.clientY, startBottom: agentBottom, moved: false };
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function moveDrag(event: PointerEvent<HTMLButtonElement>) {
    const current = drag.current;
    if (!current || current.pointerId !== event.pointerId) return;
    const delta = current.startY - event.clientY;
    if (Math.abs(delta) > 4) current.moved = true;
    if (current.moved) {
      suppressClick.current = true;
      setAgentBottom(clampBottom(current.startBottom + delta));
    }
  }

  function endDrag(event: PointerEvent<HTMLButtonElement>) {
    if (drag.current?.pointerId !== event.pointerId) return;
    drag.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  }
  return (
    <>
      {!hideAgent && (
        <button type="button" aria-label="Hablar con Mica, tu asesora contable"
          onPointerDown={startDrag} onPointerMove={moveDrag}
          onPointerUp={endDrag} onPointerCancel={endDrag} onLostPointerCapture={endDrag}
          onClick={() => {
            if (suppressClick.current) return;
            toast("Pronto podrás hablar con Mica, tu asesora contable");
          }}
          style={{ bottom: agentBottom }}
          className="fixed right-[max(1rem,calc(50%-215px+1rem))] z-50 h-16 w-16 touch-none select-none cursor-grab overflow-hidden rounded-full bg-white shadow-[0_8px_24px_rgba(89,0,106,0.35)] ring-4 ring-surface transition-transform hover:scale-105 active:scale-95 active:cursor-grabbing">
          <Image src="/mica-avatar.jpg" alt="" width={64} height={64} draggable={false} className="pointer-events-none h-full w-full object-cover" />
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
