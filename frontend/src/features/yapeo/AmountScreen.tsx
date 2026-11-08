"use client";

import clsx from "clsx";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useMemo, useState } from "react";

import { Icon } from "@/components/ui/Icon";
import { useToast } from "@/components/ui/Toast";
import { useWallets } from "@/features/wallets/api";
import { WalletPickerSheet } from "@/features/wallets/components/WalletPickerSheet";
import type { Category } from "@/lib/api/types";
import { formatMoney } from "@/lib/format";
import { useStoredState } from "@/lib/use-session-storage";

import { useYapeo } from "./api";
import { ContactSheet, type Recipient } from "./ContactSheet";
import { Keypad } from "./Keypad";
import { allowsCategories, amountError, CATEGORIES, CONTACTS, DEFAULT_MERCHANT, MESSAGE_MAX, pressKey, type Key } from "./model";

/**
 * Pantalla de monto ("Yapear a …"). Flujo contacto (botón YAPEAR) o comercio (QR).
 * El backend es la fuente de verdad: saldo, límites y categorías se validan allá.
 */
export function AmountScreen() {
  const router = useRouter();
  const params = useSearchParams();
  const toast = useToast();
  const yapeo = useYapeo();
  const { data } = useWallets();
  const isQr = params.get("flujo") === "qr";

  const [lastContact, setLastContact] = useStoredState<Recipient>("mica-last-contact", { name: CONTACTS[0].name, phone: CONTACTS[0].phone.replace(/\D/g, "") }, "local");
  const [chosen, setChosen] = useState<Recipient | null>(null);
  const merchant = params.get("para") || DEFAULT_MERCHANT;
  const recipient: Recipient = useMemo(() => (isQr ? { name: merchant } : chosen ?? lastContact), [isQr, merchant, chosen, lastContact]);

  const [walletId, setWalletId] = useState(params.get("wallet"));
  const wallets = data?.items ?? [];
  const wallet = wallets.find((w) => w.id === walletId) ?? wallets.find((w) => w.is_primary);

  const [amount, setAmount] = useState("0");
  const [message, setMessage] = useState("");
  const [category, setCategory] = useState<Category | null>(null);
  const [sheet, setSheet] = useState<"contact" | "wallet" | null>(null);
  const canCategorize = allowsCategories(wallet);

  const onKey = useCallback((key: Key) => setAmount((current) => pressKey(current, key)), []);

  function chooseCategory(code: Category) {
    // Elegir una categoría bloquea el mensaje; tocarla de nuevo lo libera.
    setCategory((current) => (current === code ? null : code));
    setMessage("");
  }

  const submit = useCallback(async () => {
    if (!wallet || yapeo.isPending) return;
    const value = Number(amount);
    const problem = amountError(value, Number(wallet.balance));
    if (problem) return toast(problem);
    try {
      const operation = await yapeo.mutateAsync({
        from_wallet_id: wallet.id,
        amount: value.toFixed(2),
        counterparty: { type: recipient.name.startsWith("Celular") ? "PHONE" : isQr ? "MERCHANT" : "CONTACT", name: recipient.name, phone: recipient.phone ?? null },
        category: canCategorize ? category : null,
        message: category ? null : message.trim() || null,
      });
      if (!isQr) setLastContact(recipient);
      router.replace(`/constancia/${operation.movement.id}`);
    } catch (err) {
      toast(err instanceof Error ? err.message : "No pudimos completar el yapeo.");
    }
  }, [wallet, yapeo, amount, recipient, isQr, canCategorize, category, message, router, toast, setLastContact]);

  const selectedCategory = CATEGORIES.find((c) => c.code === category);

  return (
    <main className="flex min-h-dvh flex-col">
      <header className="flex items-center justify-between px-4 pt-4">
        <div className="flex items-center gap-3">
          <button type="button" aria-label="Volver" onClick={() => router.back()} className="flex h-10 w-10 items-center justify-center rounded-full hover:bg-surface-container-high">
            <Icon name="arrow_back" className="text-[24px]" />
          </button>
          <span className="text-headline">Yapear a</span>
        </div>
        <button type="button" aria-label="Cerrar" onClick={() => router.replace("/")} className="flex h-10 w-10 items-center justify-center rounded-full hover:bg-surface-container-high">
          <Icon name="close" className="text-[24px]" />
        </button>
      </header>

      <section className="flex flex-1 flex-col items-center px-4 pt-4">
        <h1>
          {isQr ? (
            <span className="text-[24px] font-extrabold text-primary-container">{recipient.name}</span>
          ) : (
            <button type="button" onClick={() => setSheet("contact")} aria-label="Cambiar destinatario"
              className="inline-flex items-center gap-1 text-[24px] font-extrabold text-primary-container">
              {recipient.name}<Icon name="expand_more" className="text-[24px] opacity-70" />
            </button>
          )}
        </h1>
        <button type="button" onClick={() => setSheet("wallet")}
          className="mt-2 flex items-center gap-2 rounded-full bg-surface-container-high px-4 py-1.5 text-caption">
          <span className="h-2 w-2 rounded-full bg-secondary" />
          <span>Desde: <strong className="text-primary-container">{wallet?.name ?? "…"}</strong> (S/ {wallet ? formatMoney(wallet.balance) : "—"})</span>
          <Icon name="expand_more" className="text-[18px]" />
        </button>

        <p className="mt-6 flex items-baseline gap-2" aria-live="polite">
          <span className="text-[34px] font-bold text-primary-fixed-dim">S/</span>
          <span data-testid="amount" className="text-[64px] font-extrabold leading-none text-primary-container">{amount}</span>
        </p>
        <p className="mt-3 rounded-full bg-surface-container-high px-3 py-1 text-caption text-on-surface-variant">
          Límite por yapeo S/500, límite total por día S/2,000
        </p>

        <label className="mt-6 flex w-full max-w-[260px] items-center gap-2 border-b border-outline-variant/60 pb-1">
          <Icon name="edit_note" className="text-[20px] text-on-surface-variant" />
          <input aria-label="Agregar mensaje" placeholder="Agregar mensaje" maxLength={MESSAGE_MAX}
            value={selectedCategory ? `${selectedCategory.emoji} ${selectedCategory.label}` : message} readOnly={Boolean(selectedCategory)}
            onChange={(e) => setMessage(e.target.value)}
            className={clsx("flex-1 bg-transparent text-center text-sm outline-none", selectedCategory && "cursor-default text-primary-container")} />
        </label>

        {canCategorize && (
          <div className="mt-3 flex flex-col items-center gap-2">
            {CATEGORIES.map((c) => (
              <button key={c.code} type="button" data-category={c.code} aria-pressed={category === c.code} onClick={() => chooseCategory(c.code)}
                className={clsx("flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-caption", category === c.code ? "border-primary-container bg-primary-container text-white" : "border-outline-variant/30 bg-surface-container-low")}>
                <span>{c.emoji}</span>{c.label}
              </button>
            ))}
          </div>
        )}
      </section>

      <div className="mt-4 flex gap-3 px-4 pb-3">
        <button type="button" onClick={() => toast("Otros bancos: próximamente")} className="h-12 flex-1 rounded-full border-2 border-secondary text-label text-secondary">Otros bancos</button>
        <button type="button" onClick={submit} disabled={yapeo.isPending} data-testid="pay"
          className="h-12 flex-1 rounded-full bg-secondary-fixed-dim text-label text-on-secondary-fixed shadow-md disabled:opacity-60">
          {yapeo.isPending ? "Yapeando…" : "Yapear"}
        </button>
      </div>
      <Keypad onKey={onKey} onEnter={submit} />

      <ContactSheet open={sheet === "contact"} current={recipient.name} onClose={() => setSheet(null)}
        onChoose={(r) => { setChosen(r); setSheet(null); }} />
      <WalletPickerSheet open={sheet === "wallet"} onClose={() => setSheet(null)} wallets={wallets} eyebrow="Cambiar billetera"
        onPick={(w) => { setWalletId(w.id); if (!w.is_business) setCategory(null); setSheet(null); }} />
    </main>
  );
}
