"use client";

import clsx from "clsx";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Icon } from "@/components/ui/Icon";
import { SkeletonRows } from "@/components/ui/Skeleton";
import type { Movement, Wallet } from "@/lib/api/types";
import { formatSigned, whenLabel } from "@/lib/format";
import { useStoredState } from "@/lib/use-session-storage";

import { useMovements } from "./api";
import { MovementDetailSheet } from "./MovementDetailSheet";

/** "Mostrar movimientos": plegable, filtros por billetera y skeleton mientras carga. */
export function MovementsPanel({ wallets }: { wallets: Wallet[] }) {
  const router = useRouter();
  const [open, setOpen] = useStoredState("mica-movements-open", false);
  const [filter, setFilter] = useStoredState<string | null>("mica-movements-filter", null);
  const [detail, setDetail] = useState<Movement | null>(null);
  const activeFilter = wallets.some((w) => w.id === filter) ? filter : null;
  const { data, isPending, isFetching } = useMovements(activeFilter ?? undefined, open);

  function openMovement(movement: Movement) {
    // Los yapeos se ven como constancia; las transferencias, en una hoja de detalle.
    if (movement.direction === "TRANSFER") setDetail(movement);
    else router.push(`/constancia/${movement.id}`);
  }

  return (
    <section className="mt-2 px-4">
      <div className="overflow-hidden rounded-[2rem] bg-surface-container-lowest shadow-sm">
        <button type="button" aria-expanded={open} onClick={() => setOpen(!open)}
          className="flex w-full items-center gap-2 px-4 py-4 hover:bg-surface-container-low">
          <Icon name="receipt_long" filled className="text-[24px] text-primary-container" />
          <span className="flex-1 text-left text-[15px] font-bold text-primary-container">{open ? "Ocultar movimientos" : "Mostrar movimientos"}</span>
          <Icon name="expand_more" className={clsx("text-[22px] text-outline transition-transform duration-200", open && "rotate-180")} />
        </button>
        {open && (
          <>
            <div className="no-scrollbar flex gap-1 overflow-x-auto px-4 pb-2" role="tablist" aria-label="Filtrar por billetera">
              {[{ id: null, name: "Todas" }, ...wallets].map((w) => (
                <button key={w.id ?? "all"} type="button" role="tab" aria-selected={activeFilter === w.id} onClick={() => setFilter(w.id)}
                  className={clsx("whitespace-nowrap rounded-full px-3 py-1.5 text-caption font-semibold", activeFilter === w.id ? "bg-primary-container text-on-primary" : "bg-surface-container-high")}>
                  {w.name}
                </button>
              ))}
            </div>
            {isPending || (isFetching && !data) ? (
              <SkeletonRows rows={4} />
            ) : data && data.items.length > 0 ? (
              <ul data-testid="movements">
                {data.items.map((m) => (
                  <li key={m.id}>
                    <button type="button" onClick={() => openMovement(m)} aria-label={`Ver detalle: ${m.title}`}
                      className="flex w-full items-center justify-between gap-2 border-t border-surface-container-high px-4 py-3.5 text-left hover:bg-surface-container-low">
                      <div className="min-w-0">
                        <p className="truncate text-[15px] font-bold">{m.title}</p>
                        <p className="mt-0.5 truncate text-caption text-on-surface-variant">{whenLabel(m.occurred_at)} - {subtitle(m)}</p>
                        {(m.category_label || m.note) && (
                          <p className="mt-0.5 truncate text-caption text-on-surface-variant">
                            <span className="font-semibold text-on-surface">Descripción: </span>{m.category_label || m.note}
                          </p>
                        )}
                      </div>
                      <span className={clsx("shrink-0 text-[15px] font-bold", m.direction === "OUT" ? "text-tertiary-container" : "text-on-surface")}>{formatSigned(m.amount)}</span>
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="border-t border-surface-container-high px-4 py-6 text-center text-sm text-on-surface-variant">Aún no hay movimientos en esta billetera</p>
            )}
          </>
        )}
      </div>
      <MovementDetailSheet movement={detail} onClose={() => setDetail(null)} />
    </section>
  );
}

function subtitle(movement: Movement): string {
  if (movement.direction === "TRANSFER" && movement.from_wallet && movement.to_wallet) return `${movement.from_wallet.name} → ${movement.to_wallet.name}`;
  return movement.wallets[0]?.name ?? "";
}
