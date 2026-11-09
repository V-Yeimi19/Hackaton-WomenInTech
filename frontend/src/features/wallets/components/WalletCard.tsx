"use client";

import clsx from "clsx";

import { Icon } from "@/components/ui/Icon";
import type { Wallet } from "@/lib/api/types";
import { formatMoney, MASK } from "@/lib/format";

import { isEmoji, WALLET_COLORS, WALLET_ICON, walletTag } from "../model";

type WalletCardProps = {
  wallet: Wallet;
  shown: boolean;
  onToggleShown: () => void;
  onOptions: () => void;
  onQr: () => void;
  onSimulate?: () => void;
  simulating?: boolean;
};

const CORNER_COLORS: Record<string, string> = {
  purple: WALLET_COLORS.purple.corner,
  teal: WALLET_COLORS.teal.corner,
  magenta: WALLET_COLORS.magenta.corner,
  night: WALLET_COLORS.night.corner,
};

/** Tarjeta del carrusel: la Principal en morado, el resto en blanco con su etiqueta. */
export function WalletCard({ wallet, shown, onToggleShown, onOptions, onQr, onSimulate, simulating }: WalletCardProps) {
  const primary = wallet.is_primary;
  const walletIcon = isEmoji(wallet.icon) ? wallet.icon : <Icon name={primary ? "credit_card" : WALLET_ICON[wallet.role]} className="text-[20px]" />;
  const iconClass = clsx("flex h-7 w-9 shrink-0 items-center justify-center rounded-full text-[18px]", primary ? "bg-white/15 text-secondary-fixed" : "bg-secondary-container/50 text-on-secondary-container");
  return (
    <article
      data-wallet={wallet.id}
      className={clsx(
        "relative grid h-[200px] w-[290px] shrink-0 snap-start grid-rows-[32px_1fr_26px] overflow-hidden rounded-[2rem] p-4",
        primary ? "bg-gradient-to-r from-primary-container to-[#8c3298] text-on-primary shadow-md" : "bg-surface-container-lowest text-on-surface shadow-sm",
      )}
    >
      {!primary && <div className={clsx("pointer-events-none absolute right-0 top-0 h-24 w-24 rounded-bl-full", CORNER_COLORS[wallet.color ?? ""] ?? "bg-secondary-fixed/20")} />}
      <div className="z-10 flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-1">
            <h3 className="truncate text-[14px] font-bold leading-[17px]">{wallet.name}</h3>
            {primary && <Icon name="verified" filled className="text-[15px] text-secondary-fixed" />}
          </div>
          {primary && <p className="text-[11px] leading-[15px] font-semibold text-on-primary-container">{walletTag(wallet)}</p>}
        </div>
        <div className="flex shrink-0 items-center gap-1">
          {!primary && (
            <span className={clsx("rounded-full px-2 py-0.5 text-[11px] leading-[15px] font-semibold", wallet.purpose === "SAVINGS" ? "bg-tertiary-fixed text-tertiary" : "bg-secondary-container text-on-secondary-container")}>
              {walletTag(wallet)}
            </span>
          )}
          <button type="button" aria-label="Opciones de billetera" onClick={onOptions}
            className={clsx("-my-1 -mr-2 flex h-8 w-8 items-center justify-center rounded-full", primary ? "hover:bg-white/10" : "text-on-surface-variant hover:bg-surface-container-high")}>
            <Icon name="more_vert" className="text-[20px]" />
          </button>
        </div>
      </div>

      <div className="z-10 flex min-w-0 items-center gap-2">
        {onSimulate ? (
          <button type="button" onClick={onSimulate} disabled={simulating} aria-busy={simulating} aria-label={`Simular yapeos para ${wallet.name}`} className={clsx(iconClass, "focus-visible:outline-2 focus-visible:outline-primary active:scale-95")}>
            {walletIcon}
          </button>
        ) : <span className={iconClass}>{walletIcon}</span>}
        <div className="min-w-0 flex-1">
          <span className={clsx("block text-[12px] font-bold leading-4", primary ? "text-on-primary-container" : "text-on-surface-variant")}>Saldo digital</span>
          <div className="flex items-baseline gap-0.5">
            <span className="text-[20px] font-semibold leading-7">S/</span>
            <span data-testid="wallet-balance" className="text-[30px] font-bold leading-9 tracking-tight whitespace-nowrap">{shown ? formatMoney(wallet.balance) : MASK}</span>
            <button type="button" onClick={onToggleShown} aria-label={shown ? "Ocultar saldo" : "Mostrar saldo"}
              className="ml-2 flex h-8 w-8 shrink-0 items-center justify-center self-center rounded-full opacity-70 hover:opacity-100">
              <Icon name={shown ? "visibility" : "visibility_off"} className="text-[18px]" />
            </button>
          </div>
          <p className="mt-1 text-xs" data-testid="wallet-cash-balance">Efectivo: {wallet.cash_balance == null ? "por definir con Mica" : shown ? `S/ ${formatMoney(wallet.cash_balance)}` : MASK}</p>
        </div>
      </div>

      <button type="button" onClick={onQr}
        className={clsx("z-10 flex w-full items-center justify-center gap-1 rounded-full text-[12px] leading-4 font-bold", primary ? "bg-white/15 hover:bg-white/25" : "bg-surface-container-high text-primary-container")}>
        <Icon name="qr_code_2" className="text-[15px]" />
        Ver QR
      </button>
    </article>
  );
}
