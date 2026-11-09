"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";

import { Icon } from "@/components/ui/Icon";
import { useToast } from "@/components/ui/Toast";
import { useMovement } from "@/features/movements/api";
import { formatShort, receiptDate } from "@/lib/format";

const MICA_ADS = [
  { key: "agent", title: "Habla con Mica", text: "Tu asesora personal para tu negocio", bg: "bg-white", avatar: true, toast: "Pronto podrás hablar con Mica, tu asesora personal" },
  { key: "summary", title: "Tu resumen de la semana", text: "Mica te dice cuánto ganó tu negocio", bg: "bg-gradient-to-r from-secondary-fixed to-secondary-fixed-dim", icon: "insights", toast: "Tu resumen semanal con Mica: próximamente" },
  { key: "goals", title: "Separa para tus metas", text: "Mica te sugiere cuánto apartar", bg: "bg-gradient-to-r from-primary-fixed to-primary-fixed-dim", icon: "savings", toast: "Metas de ahorro con Mica: próximamente" },
];

/** Constancia de un yapeo enviado o recibido, con los datos reales del servidor. */
export function ReceiptScreen({ movementId }: { movementId: string }) {
  const router = useRouter();
  const toast = useToast();
  const { data: movement, isPending, isError } = useMovement(movementId);

  if (isPending) {
    return <main className="flex min-h-dvh items-center justify-center bg-primary-container text-white" aria-busy="true">Cargando constancia…</main>;
  }
  if (isError || !movement) {
    return (
      <main className="flex min-h-dvh flex-col items-center justify-center gap-4 bg-primary-container p-6 text-center text-white">
        <p>No encontramos esta constancia.</p>
        <button type="button" onClick={() => router.replace("/")} className="rounded-full bg-secondary-fixed px-6 py-3 font-bold text-on-secondary-fixed">Volver al inicio</button>
      </main>
    );
  }

  const received = movement.direction === "IN";
  const cash = movement.medium === "CASH";
  const wallet = movement.wallets[0];
  const { date, time } = receiptDate(movement.occurred_at);
  const rows: [string, string][] = [
    ...(cash ? [["Medio", "Efectivo declarado"]] as [string, string][] : [["Nro. de celular", movement.counterparty_phone_masked ?? "*** *** 321"], ["Destino", "Yape"]] as [string, string][]),
    [received ? "Billetera destino" : "Billetera origen", wallet?.name ?? "—"],
    ...(movement.category_label || movement.note ? ([["Descripción", movement.category_label || movement.note || ""]] as [string, string][]) : []),
    ["Nro. de operación", movement.operation_number],
  ];

  return (
    <main className="min-h-dvh bg-primary-container px-4 pb-8 pt-4 text-white">
      <header className="flex items-center justify-between">
        <span className="flex items-center gap-2">
          <span className="flex h-7 w-7 items-center justify-center rounded-full bg-secondary-container text-[12px] font-bold text-primary-container">S/</span>
          <span className="text-[24px] font-extrabold italic">{cash ? "Mica" : "yape"}</span>
        </span>
        <button type="button" aria-label="Cerrar" onClick={() => router.replace("/")} className="flex h-10 w-10 items-center justify-center rounded-full bg-white/15">
          <Icon name="close" className="text-[22px]" />
        </button>
      </header>

      <section className="mt-4 rounded-3xl bg-white p-5 text-on-surface shadow-lg">
        <div className="flex items-center justify-between">
          <h1 className="text-[20px] font-extrabold text-primary-container">{cash ? (received ? "Ingreso en efectivo" : "Gasto en efectivo") : received ? "¡Te yapearon!" : "¡Yapeaste!"}</h1>
          <button type="button" onClick={() => toast("Constancia copiada al portapapeles")} className="flex items-center gap-1 text-sm font-bold text-secondary">
            <Icon name="share" className="text-[18px]" />Compartir
          </button>
        </div>
        <p className="mt-2 flex items-baseline gap-1"><span className="text-[26px] font-extrabold">S/</span>
          <span data-testid="receipt-amount" className="text-[42px] font-extrabold leading-none">{formatShort(movement.amount)}</span></p>
        <p className="mt-1 text-[18px] font-bold">{movement.counterparty_name ?? movement.title}</p>
        <p className="mt-1 flex items-center gap-2 text-sm text-on-surface-variant">
          <Icon name="calendar_today" className="text-[16px]" />{date}<span className="text-outline-variant">|</span>
          <Icon name="schedule" className="text-[16px]" />{time}
        </p>
        {!cash && <div className="mt-4 flex items-center justify-between border-y border-surface-container-high py-3">
          <span className="text-[11px] font-extrabold uppercase tracking-wider text-outline">Código de seguridad</span>
          <span className="flex gap-1.5" data-testid="security-code">
            {movement.security_code.split("").map((d, i) => (
              <span key={i} className="flex h-7 w-7 items-center justify-center rounded bg-surface-container-high text-sm font-bold">{d}</span>
            ))}
          </span>
        </div>}
        <p className="mt-3 text-[11px] font-extrabold uppercase tracking-wider text-outline">Datos de la transacción</p>
        <dl className="mt-1">
          {rows.map(([label, value]) => (
            <div key={label} className="flex items-start justify-between gap-4 py-1.5 text-sm">
              <dt className="text-on-surface-variant">{label}</dt>
              <dd className="text-right font-bold">{value}</dd>
            </div>
          ))}
        </dl>
      </section>

      <button type="button" onClick={() => router.replace(cash ? "/" : "/?yapear=1")}
        className="mt-4 flex h-12 w-full items-center justify-center gap-2 rounded-full bg-secondary-container text-[15px] font-bold text-on-secondary-container shadow-md">
        <Icon name="send" className="text-[20px]" />{cash ? "Volver a mis billeteras" : "Nuevo yapeo"}
      </button>
      <button type="button" onClick={() => toast("Ayuda: próximamente")} className="mx-auto mt-3 flex items-center gap-2 text-sm font-semibold text-white/90">
        <Icon name="headphones" className="text-[18px]" />Necesito ayuda
      </button>

      <section className="mt-4 rounded-2xl bg-[#5d176b] p-3">
        <p className="flex items-center gap-1.5 text-sm font-bold">Más con Mica
          <span className="rounded bg-secondary-fixed px-1.5 text-[10px] font-extrabold uppercase text-on-secondary-fixed">Nuevo</span></p>
        <div className="no-scrollbar mt-2 flex snap-x snap-mandatory gap-2 overflow-x-auto">
          {MICA_ADS.map((ad) => (
            <button key={ad.key} type="button" onClick={() => ad.key === "agent" ? router.push("/mica") : toast(ad.toast)}
              className={`flex w-[86%] shrink-0 snap-start items-center gap-2.5 rounded-xl p-2.5 text-left text-on-surface ${ad.bg}`}>
              {ad.avatar ? <Image src="/mica-avatar.jpg" alt="" width={44} height={44} className="h-11 w-11 rounded-full object-cover" /> : (
                <span className="flex h-11 w-11 items-center justify-center rounded-full bg-white/70 text-primary-container"><Icon name={ad.icon!} className="text-[24px]" /></span>
              )}
              <span className="min-w-0 flex-1"><span className="block text-[13px] font-extrabold text-primary-container">{ad.title}</span>
                <span className="block text-[11px] text-on-surface-variant">{ad.text}</span></span>
              <Icon name="chevron_right" className="text-[20px] text-primary-container" />
            </button>
          ))}
        </div>
      </section>
    </main>
  );
}
