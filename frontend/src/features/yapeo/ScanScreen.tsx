"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Icon } from "@/components/ui/Icon";
import { useToast } from "@/components/ui/Toast";
import { useWallets } from "@/features/wallets/api";
import { WalletPickerSheet } from "@/features/wallets/components/WalletPickerSheet";

import { DEFAULT_MERCHANT } from "./model";

/** Escáner simulado: se elige la billetera recién después de detectar el QR. */
export function ScanScreen() {
  const router = useRouter();
  const toast = useToast();
  const { data } = useWallets();
  const [detected, setDetected] = useState(false);

  function detect(message = "QR detectado") {
    toast(message);
    setTimeout(() => setDetected(true), 400);
  }

  return (
    <main className="relative flex min-h-dvh flex-col bg-primary text-on-primary">
      <button type="button" aria-label="Volver" onClick={() => router.back()}
        className="absolute left-4 top-4 z-10 flex h-11 w-11 items-center justify-center rounded-full bg-primary/70">
        <Icon name="arrow_back" className="text-[24px]" />
      </button>
      <button type="button" onClick={() => detect()} aria-label="Simular escaneo de QR"
        className="relative flex flex-1 flex-col items-center justify-center overflow-hidden bg-gradient-to-b from-primary/80 via-primary-container/40 to-primary">
        <span className="absolute top-5 flex items-center gap-2 rounded-full bg-primary/60 px-3 py-1.5 text-caption font-bold">
          <span className="h-2 w-2 animate-pulse rounded-full bg-secondary-fixed" />BUSCANDO QR
        </span>
        <span className="relative flex h-60 w-60 items-center justify-center rounded-[2rem] border-4 border-secondary-fixed/90">
          <span className="absolute inset-x-6 top-1/2 h-0.5 animate-pulse bg-secondary-fixed shadow-[0_0_12px_#56faeb]" />
          <Icon name="center_focus_weak" className="text-[40px] text-secondary-fixed" />
        </span>
        <span className="mt-4 rounded-full bg-secondary-fixed px-3 py-1.5 text-caption font-bold text-on-secondary-fixed">Toca la cámara para simular el escaneo</span>
        <span className="mt-3 flex items-center gap-2 rounded-full bg-primary/80 px-4 py-2 text-sm">
          <Icon name="qr_code_scanner" className="text-[18px] text-secondary-fixed" />Apunta al código QR para pagar
        </span>
      </button>
      <div className="-mt-4 px-2 pb-3">
        <div className="flex flex-col gap-4 rounded-[2rem] bg-gradient-to-br from-primary-container to-primary p-4 shadow-[0_-8px_32px_rgba(89,0,106,0.35)]">
          <div className="mx-auto h-1 w-10 rounded-full bg-white/30" />
          <div className="flex items-center gap-3">
            <span className="flex h-11 w-11 items-center justify-center rounded-full bg-white/10"><Icon name="qr_code_scanner" className="text-[24px] text-secondary-fixed" /></span>
            <div><p className="text-[15px] font-bold">Escanea el QR del comercio</p>
              <p className="text-caption text-on-primary-container">Después eliges de qué billetera pagar.</p></div>
          </div>
          <button type="button" onClick={() => detect("QR detectado en la foto")} className="flex h-12 items-center justify-center gap-2 rounded-full bg-white/10 text-caption font-bold hover:bg-white/20">
            <Icon name="photo_library" className="text-[20px] text-secondary-fixed" />Escanear foto
          </button>
        </div>
      </div>
      <WalletPickerSheet open={detected} onClose={() => setDetected(false)} wallets={data?.items ?? []}
        eyebrow="QR detectado" title="¿Desde qué billetera pagas?" subtitle={DEFAULT_MERCHANT}
        onPick={(w) => router.push(`/yapear?wallet=${w.id}&flujo=qr&para=${encodeURIComponent(DEFAULT_MERCHANT)}`)} />
    </main>
  );
}
