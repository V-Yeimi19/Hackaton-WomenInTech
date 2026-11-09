"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Icon } from "@/components/ui/Icon";
import { MicaSheet } from "@/features/agent/MicaSheet";
import { MovementsPanel } from "@/features/movements/MovementsPanel";
import { useDemoYapeos } from "@/features/wallets/DemoYapeos";
import { useWallets } from "@/features/wallets/api";
import { QrSheet } from "@/features/wallets/components/QrSheet";
import { TransferSheet } from "@/features/wallets/components/TransferSheet";
import { WalletCard } from "@/features/wallets/components/WalletCard";
import { WalletOptionsSheet } from "@/features/wallets/components/WalletOptionsSheet";
import { WalletPickerSheet } from "@/features/wallets/components/WalletPickerSheet";
import { useBalanceVisibility } from "@/features/wallets/visibility";
import type { Wallet } from "@/lib/api/types";
import { formatMoney, MASK } from "@/lib/format";

import { BottomBar } from "./BottomBar";
import { SideMenu } from "./SideMenu";
import { TopHeader } from "./TopHeader";

type Overlay = { kind: "menu" } | { kind: "mica" } | { kind: "picker" } | { kind: "manage" } | { kind: "transfer" } | { kind: "qr"; wallet: Wallet } | { kind: "options"; wallet: Wallet } | null;

/** Inicio: compone las secciones; cada una es dueña de su lógica. */
export function HomeScreen() {
  const router = useRouter();
  const params = useSearchParams();
  const { data, isPending, isError, refetch } = useWallets();
  const visibility = useBalanceVisibility();
  const demo = useDemoYapeos();
  const [overlay, setOverlay] = useState<Overlay>(null);
  const wallets = data?.items ?? [];

  // "Nuevo yapeo" desde una constancia vuelve aquí con ?yapear=1 y abre la hoja.
  useEffect(() => {
    if (params.get("yapear") === "1") {
      setOverlay({ kind: "picker" });
      router.replace("/", { scroll: false });
    }
  }, [params, router]);

  const close = () => setOverlay(null);

  return (
    <main className="pb-28">
      <TopHeader onOpenMenu={() => setOverlay({ kind: "menu" })} />

      <section className="mt-4">
        <div className="mb-2 flex items-center justify-between px-4">
          <div className="flex items-center gap-1">
            <h2 className="text-title font-bold">Mis Billeteras</h2>
          </div>
          <button type="button" onClick={() => setOverlay({ kind: "transfer" })}
            className="flex items-center gap-1 rounded-full bg-secondary-container/60 px-3 py-1.5 text-caption font-bold text-on-secondary-container active:scale-95">
            <Icon name="swap_horiz" className="text-[18px]" />Transferir
          </button>
        </div>

        {isError ? (
          <div className="mx-4 rounded-2xl bg-error-container p-4 text-sm text-on-error-container">
            No pudimos cargar tus billeteras.{" "}
            <button type="button" className="font-bold underline" onClick={() => refetch()}>Reintentar</button>
          </div>
        ) : (
          // La key remonta el carrusel al llegar los datos: así el snap empieza en la Principal.
          <div key={isPending ? "loading" : "ready"} className="no-scrollbar flex snap-x snap-mandatory scroll-px-4 gap-4 overflow-x-auto px-4 py-2">
            {isPending && <div className="h-[152px] w-[290px] shrink-0 animate-pulse rounded-[2rem] bg-surface-container-high" />}
            {wallets.map((w) => (
              <WalletCard key={w.id} wallet={w} shown={visibility.isShown(w.id)} onToggleShown={() => visibility.toggle(w.id)}
                onSimulate={w.role === "BUSINESS" || (w.role === "CUSTOM" && w.purpose === "BUSINESS") ? () => demo.generate(w) : undefined}
                simulating={demo.generating}
                onQr={() => setOverlay({ kind: "qr", wallet: w })} />
            ))}
            <Link href="/billeteras/nueva"
              className="flex h-[152px] w-[150px] shrink-0 snap-start flex-col items-center justify-center rounded-[2rem] border-2 border-dashed border-outline-variant bg-surface-container-low text-center">
              <span className="mb-2 flex h-12 w-12 items-center justify-center rounded-full bg-primary-container text-on-primary shadow-md"><Icon name="add" className="text-[24px]" /></span>
              <span className="text-caption font-bold text-primary-container">+ Nueva Billetera</span>
              <span className="mt-1 text-caption text-on-surface-variant">Separa gastos o negocios</span>
            </Link>
          </div>
        )}
      </section>

      <section className="mt-2 px-4">
        <button type="button" onClick={visibility.toggleTotal} aria-pressed={visibility.totalShown}
          className="flex w-full items-center gap-2 rounded-[2rem] bg-surface-container-lowest px-4 py-4 text-left shadow-sm">
          <Icon name="account_balance" filled className="text-[24px] text-primary-container" />
          <span className="flex-1 text-[15px] font-bold text-primary-container">Saldo digital total</span>
          <span data-testid="total" className="text-[15px] font-bold">S/ {visibility.totalShown && data ? formatMoney(data.total) : MASK}</span>
          <Icon name={visibility.totalShown ? "visibility" : "visibility_off"} className="text-[22px] text-outline" />
        </button>
      </section>

      <MovementsPanel wallets={wallets} />

      <BottomBar onYapear={() => setOverlay({ kind: "picker" })} onAgent={() => router.push("/mica")} hideAgent={overlay !== null} />

      <SideMenu open={overlay?.kind === "menu"} onClose={close} onMica={() => setOverlay({ kind: "mica" })} onManageWallets={() => setOverlay({ kind: "manage" })} />
      <MicaSheet open={overlay?.kind === "mica"} onClose={close} />
      <WalletPickerSheet open={overlay?.kind === "manage"} onClose={close} wallets={wallets} requireBalance={false}
        eyebrow="Gestión de billeteras" title="¿Qué billetera quieres gestionar?"
        onPick={(w) => setOverlay({ kind: "options", wallet: w })} />
      <WalletPickerSheet open={overlay?.kind === "picker"} onClose={close} wallets={wallets}
        onPick={(w) => router.push(`/yapear?wallet=${w.id}&flujo=contacto`)} />
      <TransferSheet open={overlay?.kind === "transfer"} onClose={close} wallets={wallets} />
      <QrSheet wallet={overlay?.kind === "qr" ? overlay.wallet : null} onClose={close} />
      <WalletOptionsSheet wallet={overlay?.kind === "options" ? overlay.wallet : null} wallets={wallets} onClose={close} />
    </main>
  );
}
