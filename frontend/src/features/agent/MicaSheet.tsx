"use client";

import Image from "next/image";
import { useEffect, useRef, useState } from "react";

import { BottomSheet } from "@/components/ui/BottomSheet";
import { Icon } from "@/components/ui/Icon";
import { useToast } from "@/components/ui/Toast";

import { useMe, useTelegramLink } from "./api";

const TELEGRAM_BLUE = "bg-[#229ED9]";

const COMMANDS = [
  { cmd: "/resumen", text: "Cómo te fue en la semana" },
  { cmd: "/pausar", text: "Pausa los reportes automáticos" },
  { cmd: "/ayuda", text: "Todo lo que Mica puede hacer" },
];

/** Hoja de Mica: conecta la cuenta con el bot de Telegram o abre el chat si ya está conectada. */
export function MicaSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  const toast = useToast();
  const [waiting, setWaiting] = useState(false);
  const me = useMe({ watch: open && waiting });
  const telegram = me.data?.telegram;
  const linked = telegram?.linked ?? false;
  const link = useTelegramLink(open && !!telegram?.enabled && !linked);

  // Al detectar el vínculo mientras esperábamos, avisamos una sola vez.
  const wasLinked = useRef(linked);
  useEffect(() => {
    if (linked && !wasLinked.current && waiting) {
      setWaiting(false);
      toast("¡Listo! Mica ya está en tu Telegram");
    }
    wasLinked.current = linked;
  }, [linked, waiting, toast]);

  useEffect(() => {
    if (!open) setWaiting(false);
  }, [open]);

  return (
    <BottomSheet open={open} onClose={onClose} title="Habla con Mica" eyebrow="Tu asesora contable" className="pb-8">
      <div className="mb-4 flex items-center gap-3 rounded-2xl bg-primary-fixed/50 p-3">
        <Image src="/mica-avatar.jpg" alt="" width={56} height={56} className="h-14 w-14 shrink-0 rounded-full object-cover ring-4 ring-surface" />
        <p className="text-sm text-on-surface">
          Te escribo por <b>Telegram</b> con el resumen de tu negocio y te ayudo a ordenar tus movimientos.
        </p>
      </div>

      {me.isPending ? (
        <div aria-busy="true" className="h-24 w-full animate-pulse rounded-2xl bg-surface-container-high" />
      ) : me.isError ? (
        <p className="rounded-2xl bg-error-container p-4 text-sm text-on-error-container">
          No pudimos cargar tu información.{" "}
          <button type="button" className="font-bold underline" onClick={() => me.refetch()}>Reintentar</button>
        </p>
      ) : !telegram?.enabled ? (
        <p className="rounded-2xl bg-surface-container-low p-4 text-sm text-on-surface-variant">
          Pronto podrás hablar con Mica desde aquí.
        </p>
      ) : linked ? (
        <Connected botUrl={telegram.bot_url ?? null} />
      ) : (
        <ConnectSteps
          url={link.data?.telegram_url ?? null}
          code={link.data?.code ?? null}
          loading={link.isPending}
          error={link.isError}
          retry={() => link.refetch()}
          waiting={waiting}
          onOpened={() => setWaiting(true)}
        />
      )}
    </BottomSheet>
  );
}

function Connected({ botUrl }: { botUrl: string | null }) {
  return (
    <div data-testid="mica-connected">
      <p className="mb-3 flex items-center gap-2 text-sm font-bold text-on-surface">
        <Icon name="check_circle" filled className="text-[22px] text-secondary" />
        Tu cuenta ya está conectada con Telegram
      </p>
      <ul className="mb-4 divide-y divide-outline-variant/40 rounded-2xl bg-surface-container-low">
        {COMMANDS.map((c) => (
          <li key={c.cmd} className="flex items-center gap-3 px-4 py-3 text-sm">
            <code className="font-bold text-primary-container">{c.cmd}</code>
            <span className="text-on-surface-variant">{c.text}</span>
          </li>
        ))}
      </ul>
      {botUrl && (
        <a href={botUrl} target="_blank" rel="noopener noreferrer"
          className={`flex h-12 w-full items-center justify-center gap-2 rounded-xl ${TELEGRAM_BLUE} text-label uppercase tracking-wide text-white shadow-sm active:scale-[0.98]`}>
          <Icon name="send" className="text-[20px]" />Abrir chat con Mica
        </a>
      )}
    </div>
  );
}

type ConnectStepsProps = {
  url: string | null;
  code: string | null;
  loading: boolean;
  error: boolean;
  retry: () => void;
  waiting: boolean;
  onOpened: () => void;
};

function ConnectSteps({ url, code, loading, error, retry, waiting, onOpened }: ConnectStepsProps) {
  return (
    <div data-testid="mica-connect">
      <ol className="mb-4 space-y-2 text-sm text-on-surface">
        {["Toca «Conectar con Telegram».", "En Telegram, toca «Iniciar».", "Vuelve aquí: Mica te confirmará en segundos."].map((step, i) => (
          <li key={step} className="flex items-center gap-3">
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary-container text-caption font-bold text-on-primary">{i + 1}</span>
            {step}
          </li>
        ))}
      </ol>

      {error ? (
        <p className="rounded-2xl bg-error-container p-4 text-sm text-on-error-container">
          No pudimos preparar la conexión.{" "}
          <button type="button" className="font-bold underline" onClick={retry}>Reintentar</button>
        </p>
      ) : loading ? (
        <div aria-busy="true" className="h-12 w-full animate-pulse rounded-xl bg-surface-container-high" />
      ) : url ? (
        <a href={url} target="_blank" rel="noopener noreferrer" onClick={onOpened}
          className={`flex h-12 w-full items-center justify-center gap-2 rounded-xl ${TELEGRAM_BLUE} text-label uppercase tracking-wide text-white shadow-sm active:scale-[0.98]`}>
          <Icon name="send" className="text-[20px]" />Conectar con Telegram
        </a>
      ) : (
        // Sin usuario de bot configurado: el código se envía a mano.
        <p className="rounded-2xl bg-surface-container-low p-4 text-sm">
          Envía al bot de Mica: <code className="font-bold">/start {code}</code>
        </p>
      )}

      {waiting && (
        <p role="status" className="mt-3 flex items-center justify-center gap-2 text-caption text-on-surface-variant">
          <span className="h-3 w-3 animate-spin rounded-full border-2 border-secondary border-t-transparent" />
          Esperando que toques «Iniciar» en Telegram…
        </p>
      )}
      <p className="mt-3 text-center text-caption text-on-surface-variant">
        Mica nunca te pedirá tu clave de Yape.
      </p>
    </div>
  );
}
