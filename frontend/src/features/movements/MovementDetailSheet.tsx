"use client";

import { BottomSheet } from "@/components/ui/BottomSheet";
import { Icon } from "@/components/ui/Icon";
import { useToast } from "@/components/ui/Toast";
import type { Movement } from "@/lib/api/types";
import { formatSigned, whenLabel } from "@/lib/format";

/** Detalle de una transferencia entre billeteras. */
export function MovementDetailSheet({ movement, onClose }: { movement: Movement | null; onClose: () => void }) {
  const toast = useToast();
  if (!movement) return null;
  const rows: [string, string][] = [
    ["Fecha y hora", whenLabel(movement.occurred_at)],
    ["Desde", movement.from_wallet?.name ?? "—"],
    ["Hacia", movement.to_wallet?.name ?? "—"],
    ...(movement.note ? ([["Descripción", movement.note]] as [string, string][]) : []),
    ["Nro. de operación", movement.operation_number],
  ];
  return (
    <BottomSheet open onClose={onClose} title="Detalle del movimiento">
      <span className="flex h-12 w-12 items-center justify-center rounded-full bg-secondary-container/60 text-on-secondary-container">
        <Icon name="swap_horiz" className="text-[24px]" />
      </span>
      <p className="mt-2 text-caption font-bold uppercase tracking-wider text-on-surface-variant">{movement.medium === "CASH" ? "Movimiento en efectivo confirmado" : "Transferencia entre billeteras"}</p>
      <p className="text-title">{movement.title}</p>
      <p className="mt-1 text-display">{formatSigned(movement.amount)}</p>
      <dl className="mt-4">
        {rows.map(([label, value]) => (
          <div key={label} className="flex items-start justify-between gap-4 border-t border-surface-container-high py-2.5">
            <dt className="text-sm text-on-surface-variant">{label}</dt>
            <dd className="min-w-0 break-words text-right text-[15px] font-bold">{value}</dd>
          </div>
        ))}
      </dl>
      <button type="button" onClick={() => toast("Constancia lista para compartir (simulado)")}
        className="mt-4 flex h-12 w-full items-center justify-center gap-2 rounded-xl border-2 border-secondary text-label text-secondary">
        <Icon name="share" className="text-[20px]" />Compartir constancia
      </button>
    </BottomSheet>
  );
}
