"use client";

import clsx from "clsx";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { useMemo, useRef, useState } from "react";

import { Icon } from "@/components/ui/Icon";
import { useToast } from "@/components/ui/Toast";

const SHORTCUTS = [
  { icon: "phone_iphone", label: "Recargar celular", color: "text-primary-container" },
  { icon: "water_drop", label: "Yapear servicios", color: "text-sky-500" },
  { icon: "sell", label: "Promos", color: "text-amber-500" },
  { icon: "verified_user", label: "Código de aprobación", color: "text-primary-container" },
  { icon: "payments", label: "Créditos", color: "text-secondary" },
  { icon: "storefront", label: "Tienda", color: "text-primary-container" },
  { icon: "attach_money", label: "Dólares", color: "text-emerald-600" },
  { icon: "public", label: "Remesas", color: "text-sky-600" },
  { icon: "shield", label: "Seguros y SOAT", color: "text-primary-container" },
  { icon: "directions_bus", label: "Viajar en bus", color: "text-orange-500" },
  { icon: "confirmation_number", label: "Entradas", color: "text-tertiary-container" },
];

const normalize = (text: string) => text.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");

/** Cabecera morada: saludo, buscador de funcionalidades, accesos y promociones de Mica. */
export function TopHeader({ onOpenMenu }: { onOpenMenu: () => void }) {
  const toast = useToast();
  const [query, setQuery] = useState("");
  const visible = useMemo(() => SHORTCUTS.filter((s) => normalize(s.label).includes(normalize(query.trim()))), [query]);

  return (
    <section className="rounded-b-[28px] bg-gradient-to-b from-primary-container to-primary pb-4 shadow-md">
      <div className="flex h-16 items-center justify-between px-4 text-on-primary">
        <div className="flex items-center gap-2">
          <button type="button" aria-label="Mi perfil" onClick={onOpenMenu} className="flex h-9 w-9 items-center justify-center rounded-full hover:bg-white/10">
            <Icon name="person" className="text-[26px]" />
          </button>
          <span className="text-title font-bold">Hola, Yaper@</span>
        </div>
        <div className="flex items-center gap-1">
          <button type="button" aria-label="Ayuda" onClick={() => toast("Ayuda: próximamente")} className="flex h-10 w-10 items-center justify-center rounded-full hover:bg-white/10">
            <Icon name="headset_mic" className="text-[24px]" />
          </button>
          <button type="button" aria-label="Notificaciones" className="flex h-10 w-10 items-center justify-center rounded-full hover:bg-white/10">
            <Icon name="notifications" className="text-[24px]" />
          </button>
        </div>
      </div>

      <div className="px-4">
        <label className="flex h-12 items-center gap-2 rounded-[14px] bg-surface-container-lowest px-3 shadow-sm">
          <span className="flex h-8 w-8 items-center justify-center rounded-[10px] bg-primary-fixed/60">
            <Icon name="search" className="text-[20px]" />
          </span>
          <input type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Buscar una funcionalidad"
            aria-label="Buscar una funcionalidad" className="flex-1 bg-transparent text-base outline-none placeholder:text-on-surface-variant" />
        </label>
      </div>

      <div className="mt-6 grid grid-cols-4 gap-x-2 gap-y-4 px-4">
        {visible.map((s) => (
          <button key={s.label} type="button" onClick={() => toast(`${s.label}: próximamente`)} className="flex flex-col items-center gap-1.5 active:scale-95">
            <span className="flex h-14 w-14 items-center justify-center rounded-[18px] bg-surface-container-lowest shadow-sm">
              <Icon name={s.icon} filled className={`text-[30px] ${s.color}`} />
            </span>
            <span className="text-center text-[12px] leading-tight text-on-primary">{s.label}</span>
          </button>
        ))}
        {!query && (
          <button type="button" onClick={() => toast("Ver todo: próximamente")} className="flex flex-col items-center gap-1.5 active:scale-95">
            <span className="flex h-14 w-14 items-center justify-center rounded-full border-4 border-white/70 bg-primary-fixed-dim/90 shadow-sm">
              <Icon name="add" className="text-[30px] text-primary-container" />
            </span>
            <span className="text-[12px] text-on-primary">Ver todo</span>
          </button>
        )}
      </div>
      {visible.length === 0 && <p className="mt-4 px-4 text-center text-sm text-white/80">No encontramos esa funcionalidad</p>}

      <PromoCarousel />
    </section>
  );
}

const PROMOS = [
  { tag: "Mi Negocio", title: "Separa la plata de tu negocio y de tu casa", text: "Gratis, con una billetera para cada cosa.", bg: "bg-gradient-to-br from-[#3cf3de] to-[#22d7ce]", icon: "account_balance_wallet" },
  { tag: "Nuevo", title: "Habla con Mica, tu asesora contable", text: "Resuelve tus dudas de tu negocio.", bg: "bg-surface-container-lowest", avatar: true },
  { tag: "Sin comisiones", title: "Transfiere entre tus billeteras al instante", text: "Usa el botón Transferir de abajo.", bg: "bg-gradient-to-br from-primary-fixed to-primary-fixed-dim", icon: "swap_horiz" },
];

function PromoCarousel() {
  const router = useRouter();
  const track = useRef<HTMLDivElement>(null);
  const [active, setActive] = useState(0);

  function onScroll() {
    const el = track.current;
    if (!el) return;
    const middle = el.scrollLeft + el.clientWidth / 2;
    const cards = Array.from(el.children) as HTMLElement[];
    const index = cards.reduce((best, card, i) => {
      const distance = Math.abs(card.offsetLeft + card.offsetWidth / 2 - middle);
      const bestDistance = Math.abs(cards[best].offsetLeft + cards[best].offsetWidth / 2 - middle);
      return distance < bestDistance ? i : best;
    }, 0);
    setActive(index);
  }

  return (
    <div className="mt-6">
      <div ref={track} onScroll={onScroll} className="no-scrollbar flex snap-x snap-mandatory gap-2 overflow-x-auto px-4">
        {PROMOS.map((p) => (
          <div key={p.title} className={`relative flex h-36 w-[88%] shrink-0 snap-center items-center gap-2 overflow-hidden rounded-[20px] p-4 ${p.bg}`}>
            <div className="min-w-0 flex-1">
              <span className={clsx("inline-block rounded-full px-2 py-0.5 text-[11px] font-bold leading-4", p.avatar ? "bg-secondary-container text-on-secondary-container" : "bg-primary-container text-on-primary")}>{p.tag}</span>
              <p className={clsx("mt-2 text-[18px] font-bold leading-[22px]", p.tag === "Mi Negocio" ? "text-[#002c2b]" : "text-primary-container")}>{p.title}</p>
              <p className={clsx("mt-1 text-[12px] leading-4", p.tag === "Mi Negocio" ? "text-[#004441]" : "text-on-surface-variant")}>{p.text}</p>
            </div>
            {p.avatar ? (
              <Image src="/mica-avatar.jpg" alt="" width={80} height={80} className="h-20 w-20 shrink-0 rounded-full object-cover" />
            ) : (
              <Icon name={p.icon!} filled size={64} className="shrink-0 text-primary-container" />
            )}
            {p.avatar && <button type="button" aria-label="Hablar con Mica" onClick={() => router.push("/mica")} className="absolute inset-0 rounded-[20px] focus-visible:outline-2 focus-visible:outline-primary" />}
          </div>
        ))}
      </div>
      <div aria-hidden="true" className="mt-2 flex justify-center gap-1.5">
        {PROMOS.map((p, i) => (
          <span key={p.title} className={`h-1.5 rounded-full transition-all ${i === active ? "w-5 bg-white" : "w-1.5 bg-white/40"}`} />
        ))}
      </div>
    </div>
  );
}
