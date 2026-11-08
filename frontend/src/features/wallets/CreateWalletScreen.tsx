"use client";

import clsx from "clsx";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Icon } from "@/components/ui/Icon";
import { useToast } from "@/components/ui/Toast";

import { useCreateWallet, useWallets } from "./api";
import { NAME_MAX, nameError, normalizeWalletName, walletNameInput, WALLET_COLORS } from "./model";

const ICONS = ["🛍️", "☕", "💇", "🚗", "💼", "🎯"];
const COLORS = WALLET_COLORS;
type Color = keyof typeof COLORS;
type Purpose = "BUSINESS" | "SAVINGS";

/** Nueva billetera: vista previa en vivo y validación igual que el backend. */
export function CreateWalletScreen() {
  const router = useRouter();
  const toast = useToast();
  const { data } = useWallets();
  const create = useCreateWallet();
  const [name, setName] = useState("");
  const [purpose, setPurpose] = useState<Purpose>("BUSINESS");
  const [icon, setIcon] = useState(ICONS[0]);
  const [color, setColor] = useState<Color>("purple");
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const problem = nameError(name, data?.items ?? []);
    if (problem) return setError(problem);
    try {
      const normalizedName = normalizeWalletName(name);
      await create.mutateAsync({ name: normalizedName, purpose, icon, color });
      toast(`Billetera "${normalizedName}" creada`);
      router.replace("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "No pudimos crear la billetera.");
    }
  }

  return (
    <main className="min-h-dvh pb-28">
      <header className="sticky top-0 z-40 flex h-16 items-center gap-2 bg-surface/90 px-4 shadow-[0_1px_8px_rgba(0,0,0,0.04)] backdrop-blur-xl">
        <button type="button" aria-label="Volver" onClick={() => router.back()} className="flex h-10 w-10 items-center justify-center rounded-full bg-surface-container-high text-primary-container">
          <Icon name="arrow_back" className="text-[22px]" />
        </button>
        <h1 className="text-title font-bold text-primary-container">Nueva billetera</h1>
      </header>

      <form id="wallet-form" onSubmit={submit} noValidate className="flex flex-col gap-4 px-4 pt-4">
        <section className={clsx("relative overflow-hidden rounded-[2rem] bg-gradient-to-br p-4 text-white shadow-md", COLORS[color].card)}>
          <div className="flex items-center gap-3">
            <span className="flex h-12 w-12 items-center justify-center rounded-full bg-white/15 text-[24px]">{icon}</span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-title font-bold">{name.trim() || "Mi nueva billetera"}</p>
              <span className="mt-0.5 inline-block rounded-full bg-white/15 px-2 py-0.5 text-caption">{purpose === "BUSINESS" ? "Negocio" : "Ahorro"}</span>
            </div>
            <Icon name="qr_code_2" className="text-[28px] opacity-90" />
          </div>
          <p className="mt-4 text-caption opacity-80">Saldo inicial · <b>S/ 0.00</b></p>
        </section>

        <div>
          <div className="mb-2 flex justify-between">
            <label htmlFor="name" className="text-caption font-bold uppercase tracking-wider text-on-surface-variant">Nombre</label>
            <span className="text-caption text-on-surface-variant">{name.trim().length}/{NAME_MAX}</span>
          </div>
          <input id="name" maxLength={NAME_MAX} placeholder="Ej.: Delivery de postres" value={name} autoFocus autoCapitalize="sentences"
            onChange={(e) => { setName(walletNameInput(e.target.value)); setError(null); }}
            className="h-12 w-full rounded-xl border-2 border-outline-variant bg-surface-container-lowest px-3 text-base outline-none focus:border-primary-container" />
          {error ? <p role="alert" className="mt-1.5 text-sm text-error">{error}</p> : <p className="mt-1.5 text-caption text-on-surface-variant">Se verá en tu QR y en tus constancias.</p>}
        </div>

        <fieldset>
          <legend className="mb-2 text-caption font-bold uppercase tracking-wider text-on-surface-variant">Para qué es</legend>
          <div className="grid grid-cols-2 gap-2">
            {([["BUSINESS", "storefront", "Negocio"], ["SAVINGS", "savings", "Ahorro"]] as const).map(([value, ic, label]) => (
              <button key={value} type="button" aria-pressed={purpose === value}
                onClick={() => { setPurpose(value); if (value === "SAVINGS" && icon === ICONS[0]) setIcon("🎯"); }}
                className={clsx("flex items-center gap-2 rounded-2xl border-2 px-3 py-3", purpose === value ? "border-primary-container bg-primary-fixed/50" : "border-outline-variant/60 bg-surface-container-lowest")}>
                <Icon name={ic} className="text-[22px] text-primary-container" /><span className="text-[15px] font-bold">{label}</span>
              </button>
            ))}
          </div>
        </fieldset>

        <fieldset>
          <legend className="mb-2 text-caption font-bold uppercase tracking-wider text-on-surface-variant">Ícono</legend>
          <div className="grid grid-cols-6 gap-1">
            {ICONS.map((i) => (
              <button key={i} type="button" aria-label={`Ícono ${i}`} aria-pressed={icon === i} onClick={() => setIcon(i)}
                className={clsx("flex aspect-square items-center justify-center rounded-2xl border-2 text-[22px]", icon === i ? "border-primary-container bg-primary-fixed/50" : "border-transparent bg-surface-container-high")}>
                {i}
              </button>
            ))}
          </div>
        </fieldset>

        <fieldset>
          <legend className="mb-2 text-caption font-bold uppercase tracking-wider text-on-surface-variant">Color</legend>
          <div className="flex gap-2">
            {(Object.keys(COLORS) as Color[]).map((c) => (
              <button key={c} type="button" aria-label={COLORS[c].label} aria-pressed={color === c} onClick={() => setColor(c)}
                className={clsx("flex h-10 w-10 items-center justify-center rounded-full text-white", COLORS[c].dot, color === c && "ring-2 ring-primary-container ring-offset-2")}>
                {color === c && <Icon name="check" className="text-[20px]" />}
              </button>
            ))}
          </div>
        </fieldset>
      </form>

      <div className="fixed bottom-0 left-1/2 z-40 w-full max-w-[430px] -translate-x-1/2 bg-surface/95 px-4 py-3 shadow-[0_-4px_24px_rgba(116,34,132,0.08)] backdrop-blur-xl">
        <button type="submit" form="wallet-form" disabled={create.isPending}
          className="flex h-12 w-full items-center justify-center gap-2 rounded-xl bg-secondary text-label text-on-secondary disabled:opacity-60">
          <Icon name="add_circle" className="text-[20px]" />{create.isPending ? "Creando…" : "Crear billetera"}
        </button>
      </div>
    </main>
  );
}
