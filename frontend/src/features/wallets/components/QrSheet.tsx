"use client";

import { BottomSheet } from "@/components/ui/BottomSheet";
import { Icon } from "@/components/ui/Icon";
import { useToast } from "@/components/ui/Toast";
import type { Wallet } from "@/lib/api/types";

import { walletTag } from "../model";

const EXPORTS = [
  { key: "share", icon: "share", label: "Compartir", message: (n: string) => `Elige con quién compartir el QR de ${n}` },
  { key: "png", icon: "image", label: "Imagen", message: (n: string) => `QR de ${n} guardado como imagen (simulado)` },
  { key: "pdf", icon: "picture_as_pdf", label: "PDF", message: (n: string) => `QR de ${n} guardado en PDF para imprimir (simulado)` },
  { key: "print", icon: "print", label: "Imprimir", message: (n: string) => `Enviando el QR de ${n} a imprimir (simulado)` },
];

/** QR de cobro de una billetera, sin mostrar el saldo, con formas de exportar. */
export function QrSheet({ wallet, onClose }: { wallet: Wallet | null; onClose: () => void }) {
  const toast = useToast();
  if (!wallet) return null;
  return (
    <BottomSheet open onClose={onClose} title={wallet.name} subtitle={walletTag(wallet)}>
      <div className="flex flex-col items-center rounded-2xl border border-surface-container-high bg-surface p-4">
        <div className="rounded-2xl border-2 border-primary/20 bg-white p-4">
          <QrGlyph />
        </div>
        <p className="mt-2 text-center text-caption text-on-surface-variant">Escanea con Yape o cualquier billetera para pagar aquí</p>
      </div>
      <p className="mb-2 mt-4 text-caption font-bold uppercase tracking-wider text-on-surface-variant">Exportar QR</p>
      <div className="grid grid-cols-4 gap-1">
        {EXPORTS.map((e) => (
          <button key={e.key} type="button" onClick={() => toast(e.message(wallet.name))} className="flex flex-col items-center gap-1.5 rounded-[14px] py-2 hover:bg-surface-container-low">
            <span className="flex h-12 w-12 items-center justify-center rounded-full bg-primary-fixed text-primary-container"><Icon name={e.icon} className="text-[22px]" /></span>
            <span className="text-caption">{e.label}</span>
          </button>
        ))}
      </div>
    </BottomSheet>
  );
}

/** QR ilustrativo (el cobro real por QR no es parte de la demo). */
function QrGlyph() {
  const blocks = [[38, 8], [56, 8], [38, 22], [10, 40], [52, 42], [66, 40], [38, 60], [68, 58], [82, 64], [38, 82], [58, 80], [72, 78]];
  return (
    <svg viewBox="0 0 100 100" className="h-44 w-44" role="img" aria-label="Código QR de cobro">
      {[[5, 5], [67, 5], [5, 67]].map(([x, y]) => (
        <g key={`${x}-${y}`}>
          <rect x={x} y={y} width="28" height="28" rx="4" fill="#59006a" />
          <rect x={x + 5} y={y + 5} width="18" height="18" fill="#fff" />
          <rect x={x + 9} y={y + 9} width="10" height="10" rx="2" fill="#59006a" />
        </g>
      ))}
      {blocks.map(([x, y], i) => <rect key={i} x={x} y={y} width="7" height="7" rx="1" fill={i % 3 ? "#59006a" : "#006a63"} />)}
      <circle cx="50" cy="50" r="10" fill="#56faeb" />
      <circle cx="50" cy="50" r="8" fill="#742284" />
      <text x="50" y="54" fontSize="10" fontWeight="bold" fill="#56faeb" textAnchor="middle">M</text>
    </svg>
  );
}
