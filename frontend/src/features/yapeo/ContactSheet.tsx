"use client";

import clsx from "clsx";
import { useState } from "react";

import { BottomSheet } from "@/components/ui/BottomSheet";
import { Icon } from "@/components/ui/Icon";
import { formatPhoneInput, isPeruMobile } from "@/lib/format";

import { CONTACTS } from "./model";

export type Recipient = { name: string; phone?: string; type?: "CONTACT" | "MERCHANT" | "PHONE" };

const initials = (name: string) => name.split(" ").map((p) => p[0]).slice(0, 2).join("").toUpperCase();

/** "¿A quién le yapeas?": contactos frecuentes u otro número. */
export function ContactSheet({ open, current, onClose, onChoose }: {
  open: boolean; current: string; onClose: () => void; onChoose: (recipient: Recipient) => void;
}) {
  const [phone, setPhone] = useState("");
  const [error, setError] = useState<string | null>(null);

  function usePhone() {
    if (!isPeruMobile(phone)) return setError("Ingresa un celular de 9 dígitos que empiece con 9.");
    onChoose({ name: `Celular ${formatPhoneInput(phone)}`, phone: phone.replace(/\D/g, "") });
    setPhone("");
  }

  return (
    <BottomSheet open={open} onClose={onClose} eyebrow="Yapear" title="¿A quién le yapeas?">
      <ul className="flex flex-col gap-1">
        {CONTACTS.map((c) => (
          <li key={c.name}>
            <button type="button" onClick={() => onChoose({ name: c.name, phone: c.phone.replace(/\D/g, "") })}
              className={clsx("flex w-full items-center gap-3 rounded-[14px] p-2.5 text-left", c.name === current ? "bg-primary-fixed/50" : "hover:bg-surface-container-low")}>
              <span className="flex h-10 w-10 items-center justify-center rounded-full bg-primary-container text-caption font-bold text-on-primary">{initials(c.name)}</span>
              <span className="min-w-0 flex-1"><span className="block truncate text-[15px] font-bold">{c.name}</span>
                <span className="block text-caption text-on-surface-variant">{c.phone}</span></span>
              {c.name === current && <Icon name="check_circle" className="text-[20px] text-primary-container" />}
            </button>
          </li>
        ))}
      </ul>
      <p className="mb-2 mt-4 text-caption font-bold uppercase tracking-wider text-on-surface-variant">Otro número</p>
      <div className="flex gap-2">
        <label className="flex flex-1 items-center gap-2 rounded-xl border-2 border-outline-variant bg-surface px-3 focus-within:border-primary-container">
          <Icon name="smartphone" className="text-[20px] text-on-surface-variant" />
          <input aria-label="Otro número" inputMode="numeric" placeholder="9XX XXX XXX" value={phone}
            onChange={(e) => { setPhone(formatPhoneInput(e.target.value)); setError(null); }} className="h-12 flex-1 bg-transparent text-base outline-none" />
        </label>
        <button type="button" onClick={usePhone} className="rounded-xl bg-secondary px-4 text-label text-on-secondary">Usar</button>
      </div>
      {error && <p role="alert" className="mt-1.5 text-sm text-error">{error}</p>}
    </BottomSheet>
  );
}
