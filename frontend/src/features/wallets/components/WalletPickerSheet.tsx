"use client";

import clsx from "clsx";

import { BottomSheet } from "@/components/ui/BottomSheet";
import { Icon } from "@/components/ui/Icon";
import type { Wallet } from "@/lib/api/types";
import { formatMoney } from "@/lib/format";

import { WalletAvatar } from "./WalletAvatar";

type WalletPickerSheetProps = {
  open: boolean;
  onClose: () => void;
  wallets: Wallet[];
  onPick: (wallet: Wallet) => void;
  eyebrow?: string;
  title?: string;
  subtitle?: string;
};

/** "¿Desde qué billetera?": se usa al yapear, al pagar un QR y al cambiar el origen. */
export function WalletPickerSheet({ open, onClose, wallets, onPick, eyebrow = "Yapear", title = "¿Desde qué billetera?", subtitle }: WalletPickerSheetProps) {
  return (
    <BottomSheet open={open} onClose={onClose} eyebrow={eyebrow} title={title} subtitle={subtitle}>
      <ul className="flex flex-col gap-1">
        {wallets.map((w) => {
          const disabled = Number(w.balance) <= 0;
          return (
            <li key={w.id}>
              <button type="button" disabled={disabled} data-wallet-option={w.role} onClick={() => onPick(w)}
                className={clsx("flex w-full items-center gap-3 rounded-2xl p-3 text-left", disabled ? "cursor-not-allowed opacity-50" : "hover:bg-surface-container-low active:scale-[0.99]")}>
                <WalletAvatar wallet={w} />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[15px] font-bold">{w.name}</span>
                  <span className="block text-caption text-on-surface-variant">{disabled ? "Sin saldo disponible" : `Disponible: S/ ${formatMoney(w.balance)}`}</span>
                </span>
                <Icon name="chevron_right" className="text-[20px] text-outline" />
              </button>
            </li>
          );
        })}
      </ul>
    </BottomSheet>
  );
}
