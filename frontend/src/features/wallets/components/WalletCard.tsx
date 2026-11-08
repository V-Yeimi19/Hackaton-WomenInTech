"use client";

import clsx from "clsx";

import { Icon } from "@/components/ui/Icon";
import type { Wallet } from "@/lib/api/types";
import { formatMoney, MASK } from "@/lib/format";

import { isEmoji, WALLET_ICON, walletTag } from "../model";

type WalletCardProps = {
  wallet: Wallet;
  shown: boolean;
  onToggleShown: () => void;
  onOptions: () => void;
  onQr: () => void;
};

/** Tarjeta del carrusel: la Principal en morado, el resto en blanco con su etiqueta. */
export function WalletCard({ wallet, shown, onToggleShown, onOptions, onQr }: WalletCardProps) {
  const primary = wallet.is_primary;
  return (
    <article
      data-wallet={wallet.id}
      className={clsx(
        "relative flex h-[180px] w-[290px] shrink-0 snap-start flex-col justify-between overflow-hidden rounded-[2rem] p-4",
        primary ? "bg-primary-container text-on-primary shadow-md" : "bg-surface-container-lowest text-on-surface shadow-sm",
      )}
    >
      {!primary && <div className="pointer-events-none absolute right-0 top-0 h-24 w-24 rounded-bl-full bg-secondary-fixed/20" />}
      <div className="z-10 flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-1.5">
            <h3 className="truncate text-label">{wallet.name}</h3>
            {primary && <Icon name="verified" filled className="text-[16px] text-secondary-fixed" />}
          </div>
          {primary && <p className="text-caption font-semibold text-on-primary-container">{walletTag(wallet)}</p>}
        </div>
        <div className="flex shrink-0 items-center gap-1">
          {!primary && (
            <span className={clsx("rounded-full px-2 py-0.5 text-caption font-semibold", wallet.purpose === "SAVINGS" ? "bg-tertiary-fixed text-tertiary" : "bg-secondary-container text-on-secondary-container")}>
              {walletTag(wallet)}
            </span>
          )}
          <button type="button" aria-label="Opciones de billetera" onClick={onOptions}
            className={clsx("-my-1 -mr-2 flex h-8 w-8 items-center justify-center rounded-full", primary ? "hover:bg-white/10" : "text-on-surface-variant hover:bg-surface-container-high")}>
            <Icon name="more_vert" className="text-[22px]" />
          </button>
        </div>
      </div>

      <div className="z-10 my-auto flex items-center gap-3">
        <span className={clsx("flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-[20px]", primary ? "bg-white/15 text-secondary-fixed" : "bg-secondary-container/50 text-on-secondary-container")}>
          {isEmoji(wallet.icon) ? wallet.icon : <Icon name={primary ? "credit_card" : WALLET_ICON[wallet.role]} />}
        </span>
        <div>
          <span className={clsx("text-caption", primary ? "text-on-primary-container" : "text-on-surface-variant")}>Saldo disponible</span>
          <div className="flex items-baseline gap-1">
            <span className="text-title font-semibold">S/</span>
            <span data-testid="wallet-balance" className="text-[28px] font-bold leading-9">{shown ? formatMoney(wallet.balance) : MASK}</span>
            <button type="button" onClick={onToggleShown} aria-label={shown ? "Ocultar saldo" : "Mostrar saldo"}
              className="ml-1 flex h-8 w-8 items-center justify-center self-center rounded-full opacity-70 hover:opacity-100">
              <Icon name={shown ? "visibility" : "visibility_off"} className="text-[20px]" />
            </button>
          </div>
        </div>
      </div>

      <button type="button" onClick={onQr}
        className={clsx("z-10 flex w-full items-center justify-center gap-1 rounded-full py-1.5 text-caption font-bold", primary ? "bg-white/15 hover:bg-white/25" : "bg-surface-container-high text-primary-container")}>
        <Icon name="qr_code_2" className="text-[16px]" />
        Ver QR
      </button>
    </article>
  );
}
