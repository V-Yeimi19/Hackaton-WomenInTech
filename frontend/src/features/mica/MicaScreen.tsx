"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { BottomSheet } from "@/components/ui/BottomSheet";
import { Icon } from "@/components/ui/Icon";
import { useToast } from "@/components/ui/Toast";
import { useWallets } from "@/features/wallets/api";

import { MovementSummary } from "./MovementSummary";
import { ApiError } from "@/lib/api/http";
import { MicaSheet } from "@/features/agent/MicaSheet";
import { getProfile, saveProfile, getChat, sendChat, chatTurns } from "./api";

import { topSalesSuggestions } from "./suggestions";

const STEPS = ["Rubro", "Top Ventas", "Promedio", "Costos Fijos", "Reporte"];
const QUESTIONS = [
  "¿De qué es tu negocio o a qué te dedicas principalmente?",
  "¿Qué productos o servicios vendes más en tu negocio?",
  "En un día normal, ¿más o menos cuánto vendes?",
  "Para tener tu negocio abierto, ¿cuáles son tus gastos del mes?",
  "Para no interrumpirte mientras trabajas, ¿qué día y a qué hora prefieres recibir tu reporte semanal de tu negocio?",
];
const OPTIONS = [
  ["🏪 Bodega / Abarrotes", "☕ Cafetería / Comida", "👗 Ropa y Calzado", "✂️ Salón / Barbería"],
  ["Comidas y bebidas", "Productos de primera necesidad", "Prendas y accesorios", "Servicios"],
  ["Menos de S/ 100", "S/ 100 – S/ 300", "S/ 300 – S/ 500", "Más de S/ 500"],
  ["Alquiler", "Servicios", "Personal", "Ninguno"],
  ["Domingo a las 4 p. m.", "Lunes a las 12 p. m.", "Martes a las 9 a. m."],
];
const BENEFITS = [
  { icon: "query_stats", title: "Llevar el control total", text: "Monitoreo automático de ingresos y egresos diarios.", color: "bg-primary-container" },
  { icon: "savings", title: "Separar dinero sin sufrir", text: "Conoce cuánto reinvertir sin afectar tu día a día.", color: "bg-secondary" },
  { icon: "insights", title: "Reportes semanales y tips", text: "Tus días con pico de ventas y alertas de caja chica.", color: "bg-tertiary-container" },
];

function Avatar({ size = 32 }: { size?: number }) {
  return <Image src="/mica-avatar.jpg" alt="Mica" width={size} height={size} className="shrink-0 rounded-full object-cover" style={{ width: size, height: size }} />;
}

export function MicaScreen() {
  const { data, isPending, isError, refetch } = useWallets();
  const [selectedId, setSelectedId] = useState("");
  const [picker, setPicker] = useState(false);
  const [telegramOpen, setTelegramOpen] = useState(false);
  const toast = useToast();
  const wallets = (data?.items ?? []).filter((wallet) => wallet.role === "BUSINESS" || (wallet.role === "CUSTOM" && wallet.purpose === "BUSINESS"));
  const wallet = wallets.find((w) => w.id === selectedId) ?? wallets.find((w) => w.role === "BUSINESS") ?? wallets[0];


  return (
    <div className="min-h-dvh bg-surface">
      <header className="sticky top-0 z-30 shadow-sm">
        <div className="flex h-12 items-center justify-between bg-primary-container px-3.5 text-white">
          <Link href="/" className="flex items-center gap-2.5 font-bold"><span className="flex h-8 w-8 items-center justify-center rounded-full bg-white/15"><Icon name="person" size={19} /></span>Hola, Yaper@</Link>
          <div className="flex gap-4"><button aria-label="Soporte" onClick={() => toast("Completa tu perfil para conocer mejor tu negocio.")}><Icon name="headphones" size={22} /></button><button aria-label="Notificaciones" onClick={() => toast("No tienes nuevas notificaciones.")}><Icon name="notifications" size={22} /></button></div>
        </div>
        <div className="flex items-center gap-2 bg-white px-3 py-2.5">
          <Link href="/" aria-label="Volver al inicio" className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-surface-container text-primary-container"><Icon name="arrow_back" /></Link>
          <div className="relative rounded-full ring-2 ring-secondary"><Avatar size={44} /><span className="absolute bottom-0 right-0 h-3.5 w-3.5 rounded-full bg-[#25d366] ring-2 ring-white" /></div>
          <div className="min-w-0 flex-1 pl-1"><h1 className="text-lg font-extrabold text-primary-container">Mica <span className="text-sm">✨</span></h1><p className="text-[11px] font-bold text-secondary">Asesora de Negocios en vivo</p></div>
          <button aria-label="Continuar en Telegram" onClick={() => setTelegramOpen(true)} className="flex h-9 w-9 items-center justify-center rounded-full bg-[#229ED9]/10 text-[#229ED9]"><Icon name="send" size={20} /></button>

        </div>
        <div className="border-b border-outline-variant/40 bg-white px-3 pb-2.5 pt-1">
          <div className="flex items-center gap-2 rounded-full border border-outline-variant/40 bg-surface-container-low px-2.5 py-1.5">
            <Icon name="storefront" size={18} className="shrink-0 text-primary-container" />
            <p className="min-w-0 flex-1 truncate text-xs text-on-surface-variant">Billetera: <strong className="text-primary-container">{wallet?.name ?? (isPending ? "Cargando…" : "Sin billeteras de negocio")}</strong></p>
            <button onClick={() => setPicker(true)} disabled={!wallets.length} className="flex items-center gap-1 rounded-full border border-outline-variant bg-white px-3 py-1 text-[11px] font-bold disabled:opacity-40">Cambiar<Icon name="keyboard_arrow_down" size={16} /></button>
          </div>
        </div>
      </header>
      {isPending && <p role="status" className="p-6 text-center text-sm">Preparando tu chat con Mica…</p>}
      {isError && <p role="alert" className="p-6 text-center text-sm">No pudimos cargar tus billeteras. <button onClick={() => refetch()} className="font-bold text-primary underline">Reintentar</button></p>}
      {!isPending && !isError && !wallet && <p className="p-6 text-center">Crea una billetera de tipo negocio para comenzar. <Link href="/billeteras/nueva" className="font-bold text-primary underline">Crear billetera de negocio</Link></p>}
      {wallet && <Conversation key={wallet.id} walletId={wallet.id} walletName={wallet.name} />}
      <MicaSheet open={telegramOpen} onClose={() => setTelegramOpen(false)} />
      <BottomSheet open={picker} onClose={() => setPicker(false)} title="Elige tu billetera de negocio" eyebrow="Asesor Mica">
        <div className="space-y-2">{wallets.map((w) => <button key={w.id} onClick={() => { setSelectedId(w.id); setPicker(false); }} className="flex w-full items-center justify-between rounded-2xl bg-surface-container-low p-4 text-left font-bold"><span>{w.name}</span>{wallet?.id === w.id && <Icon name="check" className="text-secondary" />}</button>)}</div>
      </BottomSheet>
    </div>
  );
}

function Conversation({ walletId, walletName }: { walletId: string; walletName: string }) {
  const [answers, setAnswers] = useState<string[]>([]);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<{ role: "user" | "assistant"; content: string }[]>([]);
  const [sending, setSending] = useState(false);
  const [chatError, setChatError] = useState("");
  const [selections, setSelections] = useState<string[]>([]);
  const selected = selections.join(", ");
  const [loaded, setLoaded] = useState(false);
  const [profileVersion, setProfileVersion] = useState(0);
  const [loadAttempt, setLoadAttempt] = useState(0);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const pendingRequest = useRef<{ message: string; id: string } | null>(null);
  const field = useRef<HTMLInputElement>(null);
  const end = useRef<HTMLDivElement>(null);
  const step = answers.length;
  const storageKey = `mica-onboarding:${walletId}`;
  const quickOptions = step === 1 ? topSalesSuggestions(answers[0] ?? "") : OPTIONS[step] ?? [];

  useEffect(() => {
    let active = true;
    async function load() {
      setLoaded(false);
      setChatError("");
      try {
        const [savedProfile, page] = await Promise.all([getProfile(walletId), getChat(walletId)]);
        let profile = savedProfile;
        // Recupera la personalización anterior si aún no hay perfil en el servidor.
        if (profile.version === 0) {
          let legacy: unknown = [];
          try { legacy = JSON.parse(sessionStorage.getItem(storageKey) ?? "[]"); } catch { /* Sin datos locales. */ }
          if (Array.isArray(legacy) && legacy.length > 0 && legacy.length <= STEPS.length && legacy.every((v) => typeof v === "string" && v.trim().length > 0 && v.length <= 500)) {
            try { profile = await saveProfile(walletId, legacy, 0); }
            catch (error) {
              if (error instanceof ApiError && error.status === 409) profile = await getProfile(walletId);
              else throw error;
            }
          }
        }
        if (!active) return;
        setAnswers(profile.answers);
        setProfileVersion(profile.version);
        setMessages(chatTurns(page.items));
        setNextCursor(page.next_cursor);
        setLoaded(true);
      } catch {
        if (active) setChatError("No pude cargar tu conversación. Reintenta para continuar.");
      }
    }
    void load();
    return () => { active = false; };
  }, [storageKey, walletId, loadAttempt]);

  useEffect(() => {
    if (messages.length || sending) end.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length, sending]);

  async function loadOlder() {
    if (!nextCursor || loadingOlder) return;
    setLoadingOlder(true);
    try {
      const page = await getChat(walletId, nextCursor);
      setMessages((current) => [...chatTurns(page.items), ...current]);
      setNextCursor(page.next_cursor);
    } catch { setChatError("No pude cargar los mensajes anteriores. Intenta de nuevo."); }
    finally { setLoadingOlder(false); }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    const answer = input.trim() || selected;
    if (!answer || sending || !loaded) return;
    setSending(true);
    setChatError("");
    try {
      if (step >= STEPS.length) {
        if (pendingRequest.current?.message !== answer) {
          pendingRequest.current = { message: answer, id: crypto.randomUUID() };
        }
        const response = await sendChat(walletId, answer, pendingRequest.current.id);
        setMessages((current) => [...current, ...chatTurns([response])]);
        pendingRequest.current = null;
      } else {
        const profile = await saveProfile(walletId, [...answers, answer], profileVersion);
        setAnswers(profile.answers);
        setProfileVersion(profile.version);
        // El servidor ya conserva esta memoria para ambos canales.
        try { sessionStorage.removeItem(storageKey); } catch { /* No bloquea el guardado. */ }
      }
      setInput("");
      setSelections([]);
    } catch (error) {
      if (error instanceof ApiError && error.code === "PROFILE_VERSION_CONFLICT") {
        try {
          const profile = await getProfile(walletId);
          setAnswers(profile.answers);
          setProfileVersion(profile.version);
          setChatError("Tu perfil cambió en otra sesión. Revisa la pregunta actual antes de volver a enviar.");
        } catch { setChatError("No pude actualizar tu perfil. Recarga la página para continuar."); }
      } else setChatError("No pude guardar tu mensaje. Tu respuesta sigue escrita para que puedas reintentar.");
    } finally { setSending(false); }
  }

  return (
    <>
      <main className="space-y-3 px-4 pb-40 pt-2">
        <section className="relative overflow-hidden rounded-[32px] bg-white p-4 shadow-[0_4px_20px_rgba(116,34,132,0.06)]">
          <div className="pointer-events-none absolute -bottom-8 -left-8 h-32 w-32 rounded-full bg-secondary-fixed/30 blur-2xl" />
          <div className="pointer-events-none absolute -right-8 -top-8 h-36 w-36 rounded-full bg-primary-fixed/30 blur-2xl" />
          <div className="relative flex flex-col items-center text-center">
            <div className="relative mb-2 rounded-full bg-gradient-to-tr from-primary to-secondary-fixed p-1"><Avatar size={72} /><span className="absolute bottom-0 right-0 rounded-full bg-secondary px-1.5 py-0.5 text-[10px] font-bold text-white">● IA</span></div>
            <h2 className="text-xl font-bold">¡Hola! Soy Mica 👋</h2>
            <p className="mb-4 mt-1 text-sm leading-5 text-on-surface-variant">Tu asesora personal en Yape. He activado la lectura de tu billetera <strong className="text-primary">{walletName}</strong>.</p>
            <div className="w-full space-y-2.5 text-left">{BENEFITS.map((b) => <div key={b.title} className="flex items-start gap-3 bg-surface-container-low p-2.5"><span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-white ${b.color}`}><Icon name={b.icon} size={18} /></span><div className="text-xs leading-[17px]"><h3 className="font-bold">{b.title}</h3><p className="text-on-surface-variant">{b.text}</p></div></div>)}</div>
          </div>
        </section>
        <section aria-label="Progreso de personalización" className="bg-surface-container-low p-3.5">
          <div className="mb-2 flex items-center justify-between gap-1 text-xs"><p><strong className="text-sm text-primary">{step < STEPS.length ? `Paso ${step + 1} de ${STEPS.length}` : `${STEPS.length} de ${STEPS.length} completados`}</strong><span className="ml-1 text-on-surface-variant"> ● Personalización</span></p></div>
          <div className="mb-3 h-1.5 overflow-hidden rounded-full bg-surface-variant"><div className="h-full rounded-full bg-primary transition-all" style={{ width: `${Math.min(step + 1, STEPS.length) / STEPS.length * 100}%` }} /></div>
          <ol className="grid grid-cols-5 text-center">{STEPS.map((label, i) => <li key={label} aria-current={i === step ? "step" : undefined} className={`flex flex-col items-center gap-1 text-[10px] ${i <= step ? "font-bold text-primary" : "text-on-surface-variant/60"}`}><span className={`flex h-5 w-5 items-center justify-center rounded-full ${i <= step ? "bg-primary text-white" : "bg-surface-variant"}`}>{i < step ? "✓" : i + 1}</span>{label}</li>)}</ol>
        </section>
        <div role="log" aria-label="Conversación con Mica" aria-live="polite" className="space-y-3">
          {Array.from({ length: Math.min(step + 1, STEPS.length) }, (_, i) => <div key={i} className="space-y-3">
            <div className="flex max-w-[94%] items-end gap-2"><Avatar size={30} /><div className="rounded-[20px] bg-white p-3.5 text-sm leading-[21px] shadow-sm">{i === 0 && <p className="mb-2">A partir de hoy me encargaré de analizar tus ingresos por QR, clasificar tus gastos y darte recomendaciones accionables cada semana.</p>}<p className="font-semibold text-primary">{QUESTIONS[i]}</p><span className="mt-1 block text-right text-[10px] text-on-surface-variant/70">Recién</span></div></div>
            {answers[i] && <p className="ml-auto w-fit max-w-[85%] rounded-2xl rounded-br-sm bg-primary-container px-4 py-3 text-sm text-white">{answers[i]}</p>}
          </div>)}
          {step === STEPS.length && <>
            <div className="flex items-end gap-2"><Avatar size={30} /><p className="rounded-2xl bg-white p-4 text-sm leading-6"><strong className="text-primary">¡Gracias! Ya personalizaste tu perfil 🎉</strong><br />Guardé tus respuestas para {walletName}. Mica las recordará en la app y en Telegram. Tu horario preferido es: {answers[4]}.</p></div>
            <div className="flex items-end gap-2"><Avatar size={30} /><div className="rounded-2xl bg-white p-4 text-sm leading-6"><MovementSummary walletId={walletId} walletName={walletName} /></div></div>
          </>}
        </div>
        {loaded && step < STEPS.length && <section className="space-y-2 pl-10"><h3 className="text-[11px] font-bold uppercase tracking-wide text-on-surface-variant">{step === 3 ? "Puedes elegir varios gastos o ninguno:" : "Toca una opción rápida:"}</h3><div className="flex flex-wrap gap-2">{quickOptions.map((option) => <button key={option} type="button" aria-pressed={selections.includes(option)} onClick={() => { setSelections((current) => {
                  if (step !== 3) return [option];
                  if (option === "Ninguno") return current.includes(option) ? [] : [option];
                  const expenses = current.filter((value) => value !== "Ninguno");
                  return expenses.includes(option) ? expenses.filter((value) => value !== option) : [...expenses, option];
                }); setInput(""); }} className={`rounded-full px-3.5 py-3 text-left text-xs font-bold shadow-sm transition-colors ${selections.includes(option) ? "bg-primary-container text-white ring-2 ring-secondary-fixed" : "bg-white text-on-surface"}`}>{option}{selections.includes(option) && <span className="ml-2 text-secondary-fixed">✓</span>}</button>)}<button onClick={() => { setSelections([]); field.current?.focus(); }} className="flex items-center gap-1.5 rounded-full bg-surface-container px-4 py-2.5 text-xs font-semibold"><Icon name="edit" size={16} className="text-primary" />{step === 2 ? "Escribir monto o rango…" : step === 4 ? "Escribir día y hora…" : "Escribir otro…"}</button></div></section>}
        {nextCursor && <button type="button" disabled={loadingOlder} onClick={loadOlder} className="text-sm font-bold text-primary">{loadingOlder ? "Cargando…" : "Ver mensajes anteriores"}</button>}
        {messages.map((message, index) => <div key={index} className={`flex items-end gap-2 ${message.role === "user" ? "justify-end" : ""}`}>
          {message.role === "assistant" && <Avatar size={30} />}
          <p className={`max-w-[85%] whitespace-pre-wrap rounded-2xl px-4 py-3 text-sm leading-6 ${message.role === "user" ? "bg-primary-container text-white" : "bg-white"}`}>{message.content}</p>
        </div>)}
        {sending && <div role="status" className="space-y-2"><p className="ml-auto w-fit max-w-[85%] rounded-2xl bg-primary-container px-4 py-3 text-sm text-white">{input}</p><p className="pl-10 text-sm text-secondary">Mica está respondiendo…</p></div>}
        {chatError && <div role="alert" className="rounded-2xl bg-error-container p-3 text-sm text-error">{chatError}{!loaded && <button type="button" onClick={() => setLoadAttempt((attempt) => attempt + 1)} className="ml-2 font-bold underline">Reintentar</button>}</div>}
        <div ref={end} />
      </main>
      <footer className="fixed bottom-0 left-1/2 z-20 w-full max-w-[430px] -translate-x-1/2 bg-surface/95 px-4 pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-2 backdrop-blur-md">
        <form onSubmit={submit} className="flex items-center gap-2"><input ref={field} aria-label="Respuesta a Mica" value={input} disabled={sending || !loaded} maxLength={500} onChange={(e) => { setInput(e.target.value); setSelections([]); }} placeholder={step >= STEPS.length ? "Escribe tu mensaje a Mica…" : selected || (step === 2 ? "Ej.: S/ 150 o de S/ 100 a S/ 200" : step === 4 ? "Ej.: Viernes a las 6 p. m." : "Responde a Mica o elige una opción…")} className="h-14 min-w-0 flex-1 rounded-full bg-white px-4 text-sm shadow-sm outline-none focus:ring-2 focus:ring-primary-container disabled:opacity-60" /><button type="submit" aria-label="Enviar respuesta" disabled={(!input.trim() && !selected) || sending || !loaded} className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-secondary-fixed-dim text-on-secondary-fixed-variant shadow-md disabled:opacity-40"><Icon name="arrow_upward" /></button></form>
      </footer>
    </>
  );
}
