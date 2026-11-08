"use client";

import clsx from "clsx";
import { useState } from "react";

import { Icon } from "@/components/ui/Icon";
import type { Wallet } from "@/lib/api/types";
import { formatMoney } from "@/lib/format";

import { WalletAvatar } from "./WalletAvatar";

const SEARCH_FROM = 6;

type WalletSelectProps = {
  label: string;
  options: Wallet[];
  value: string | null;
  onChange: (walletId: string) => void;
  /** Billeteras sin saldo no se pueden elegir como origen. */
  disableEmpty?: boolean;
  hint?: (wallet: Wallet) => string;
};

/** Desplegable de billeteras: escala con buscador (≥6) y lista con altura máxima. */
export function WalletSelect({ label, options, value, onChange, disableEmpty, hint }: WalletSelectProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const selected = options.find((w) => w.id === value) ?? null;
  const filtered = options.filter((w) => w.name.toLowerCase().includes(query.trim().toLowerCase()));

  return (
    <div>
      <p className="mb-2 text-caption font-bold uppercase tracking-wider text-on-surface-variant">{label}</p>
      <button type="button" aria-expanded={open} onClick={() => setOpen((o) => !o)}
        className={clsx("flex w-full items-center gap-3 rounded-xl border-2 bg-surface px-3 py-2.5 text-left", selected ? "border-primary-container" : "border-outline-variant")}>
        {selected ? <WalletAvatar wallet={selected} size="sm" /> : (
          <span className="flex h-9 w-9 items-center justify-center rounded-full bg-surface-container-high text-on-surface-variant"><Icon name="account_balance_wallet" className="text-[18px]" /></span>
        )}
        <span className="min-w-0 flex-1">
          <span className={clsx("block truncate text-label", selected ? "text-on-surface" : "font-medium text-on-surface-variant")}>{selected ? selected.name : "Elige una billetera"}</span>
          {selected && <span className="block text-caption text-on-surface-variant">{hint ? hint(selected) : `Saldo: S/ ${formatMoney(selected.balance)}`}</span>}
        </span>
        <Icon name="expand_more" className={clsx("text-[22px] text-primary-container transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <div className="mt-1 rounded-2xl border border-surface-container-high p-1">
          {options.length >= SEARCH_FROM && (
            <label className="mb-1 flex items-center gap-2 rounded-full bg-surface-container-high px-3">
              <Icon name="search" className="text-[18px] text-on-surface-variant" />
              <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Buscar billetera" className="h-10 flex-1 bg-transparent outline-none" />
            </label>
          )}
          <div className="max-h-52 overflow-y-auto" role="listbox">
            {filtered.length === 0 && <p className="py-4 text-center text-sm text-on-surface-variant">No encontramos esa billetera</p>}
            {filtered.map((w) => {
              const disabled = disableEmpty && Number(w.balance) <= 0;
              return (
                <button key={w.id} type="button" role="option" aria-selected={w.id === value} disabled={disabled}
                  onClick={() => { onChange(w.id); setOpen(false); setQuery(""); }}
                  className={clsx("flex w-full items-center gap-3 rounded-[14px] p-2.5 text-left", w.id === value ? "bg-primary-fixed/50" : "hover:bg-surface-container-low", disabled && "cursor-not-allowed opacity-50")}>
                  <WalletAvatar wallet={w} size="sm" />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-label">{w.name}</span>
                    <span className="block text-[11px] text-on-surface-variant">{disabled ? "Sin saldo" : `Saldo: S/ ${formatMoney(w.balance)}`}</span>
                  </span>
                  {w.id === value && <Icon name="check_circle" className="text-[20px] text-primary-container" />}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
