"use client";

import Image from "next/image";
import { useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { Icon } from "@/components/ui/Icon";
import { ApiError, request } from "@/lib/api/http";
import { formatPhoneInput, isPeruMobile } from "@/lib/format";
import { resetBalanceVisibility } from "@/features/wallets/visibility";

const CONFETTI = [
  "left-[12%] top-[12%] text-secondary-fixed rotate-12",
  "right-[14%] top-[8%] text-amber-300 -rotate-12",
  "left-[16%] bottom-[16%] text-secondary-fixed -rotate-6",
];

/** Bienvenida y entrada solo con número: el BFF guarda la sesión en una cookie httpOnly. */
export function LoginScreen() {
  const queryClient = useQueryClient();
  const [step, setStep] = useState<"welcome" | "phone">("welcome");
  const [phone, setPhone] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (loading) return;
    if (!isPeruMobile(phone)) return setError("Ingresa un celular de 9 dígitos que empiece con 9.");
    setError(null);
    setLoading(true);
    try {
      await request("/api/auth/login", { method: "POST", body: { phone: phone.replace(/\D/g, "") } });
      await queryClient.cancelQueries();
      queryClient.clear();
      resetBalanceVisibility();
      // El BFF ya guardó la cookie. Una nueva navegación evita reutilizar
      // redirecciones a /login que Next haya cacheado antes de iniciar sesión.
      window.location.replace("/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No pudimos iniciar sesión.");
      setLoading(false);
    }
  }

  if (step === "welcome") {
    return (
      <main className="flex min-h-dvh flex-col bg-primary-container px-6 pb-8 pt-10 text-on-primary">
        <div className="relative flex min-h-[340px] flex-1 items-center justify-center">
          {CONFETTI.map((cls) => (
            <span key={cls} aria-hidden="true" className={`absolute text-[32px] ${cls}`}>
              〰
            </span>
          ))}
          <span aria-hidden="true" className="absolute right-[18%] bottom-[12%] h-3 w-3 rounded-full bg-amber-300" />
          <span aria-hidden="true" className="absolute left-[30%] top-[4%] h-2.5 w-2.5 rounded-full bg-secondary-fixed" />
          <Image src="/mica-avatar.jpg" alt="Mica, tu asesora personal" width={208} height={208} priority
            className="relative h-52 w-52 rounded-full object-cover shadow-2xl ring-8 ring-white/10" />
        </div>
        <div className="text-center">
          <h1 className="mt-0.00001 text-[28px] font-bold leading-11">¡Te damos la bienvenida a Mica!</h1>
          <p className="mt-2 text-base text-on-primary-container">
            Inicia sesión con tu número de celular para probar Mi Negocio. No necesitas clave.
          </p>
        </div>
        <button type="button" onClick={() => setStep("phone")}
          className="mt-8 h-12 rounded-xl bg-secondary-fixed-dim text-label uppercase tracking-wide text-on-secondary-fixed active:scale-[0.98]">
          Iniciar sesión
        </button>
      </main>
    );
  }

  return (
    <main className="flex min-h-dvh flex-col bg-primary-container px-6 pb-8 pt-6 text-on-primary">
      <button type="button" onClick={() => setStep("welcome")} aria-label="Volver"
        className="flex h-10 w-10 items-center justify-center rounded-full bg-white/10">
        <Icon name="arrow_back" className="text-[22px]" />
      </button>
      <div className="mt-6 flex items-center gap-3">
        <Image src="/mica-avatar.jpg" alt="" width={56} height={56} className="h-14 w-14 rounded-full object-cover ring-4 ring-white/10" />
        <div>
          <h1 className="text-headline">Ingresa tu número</h1>
        </div>
      </div>
      <form onSubmit={submit} noValidate className="mt-6 flex flex-col gap-4 rounded-3xl bg-surface-container-lowest p-6 text-on-surface shadow-xl">
        <label htmlFor="phone" className="text-caption font-bold uppercase tracking-wider text-on-surface-variant">
          Número de celular
        </label>
        <div className="-mt-2 flex items-center gap-2 rounded-xl border-2 border-outline-variant bg-surface px-3 focus-within:border-primary-container">
          <span className="text-label text-on-surface-variant">+51</span>
          <input id="phone" inputMode="numeric" autoComplete="tel-national" placeholder="987 654 321" autoFocus
            value={phone} onChange={(e) => { setPhone(formatPhoneInput(e.target.value)); setError(null); }}
            className="h-12 flex-1 bg-transparent text-title tracking-wide outline-none" />
        </div>
        {error && <p role="alert" className="-mt-1 text-sm text-error">{error}</p>}
        <button type="submit" disabled={loading}
          className="h-12 rounded-xl bg-secondary text-label uppercase tracking-wide text-on-secondary disabled:opacity-60">
          {loading ? "Ingresando…" : "Ingresar"}
        </button>
      </form>
      <div className="mt-4 flex items-start gap-2 rounded-2xl bg-white/10 p-3">
        <Icon name="lock" className="text-[20px] text-secondary-fixed" />
        <p className="text-sm text-on-primary-container">
          <b className="text-on-primary">No ingreses tu clave de Yape.</b>
        </p>
      </div>
    </main>
  );
}
