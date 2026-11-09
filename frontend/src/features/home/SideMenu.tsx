"use client";

import clsx from "clsx";
import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Icon } from "@/components/ui/Icon";
import { request } from "@/lib/api/http";

const ITEMS = [
  { icon: "person", label: "Mi perfil", active: true },
  { icon: "smartphone", label: "Recargar celular" },
  { icon: "payments", label: "Créditos" },
  { icon: "percent", label: "Promociones" },
  { icon: "lock", label: "Código de aprobación" },
  { icon: "request_quote", label: "Cobrar" },
];

/** Menú lateral (solo visual) con Gestión de billeteras, Mica en Telegram y Cerrar sesión funcionales. */
export function SideMenu({ open, onClose, onMica, onManageWallets }: { open: boolean; onClose: () => void; onMica: () => void; onManageWallets: () => void }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (!open) return setVisible(false);
    const frame = requestAnimationFrame(() => setVisible(true));
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => { cancelAnimationFrame(frame); window.removeEventListener("keydown", onKey); };
  }, [open, onClose]);

  async function logout() {
    await queryClient.cancelQueries();
    queryClient.clear();
    await request("/api/auth/logout", { method: "POST" }).catch(() => undefined);
    router.replace("/login");
    router.refresh();
  }

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[80] mx-auto max-w-[430px]">
      <div onClick={onClose} className={clsx("absolute inset-0 bg-inverse-surface/50 transition-opacity duration-300", visible ? "opacity-100" : "opacity-0")} />
      <nav aria-label="Menú" className={clsx("absolute bottom-0 left-0 top-0 flex w-[80%] flex-col bg-surface-container-lowest shadow-xl transition-transform duration-300", visible ? "translate-x-0" : "-translate-x-full")}>
        <div className="flex-1 pt-12">
          {ITEMS.map((item) => (
            <button key={item.label} type="button"
              className={clsx("flex w-full items-center gap-6 px-6 py-4 text-left", item.active ? "border-b border-outline-variant/40 bg-primary-fixed/40" : "hover:bg-surface-container-low")}>
              <Icon name={item.icon} className="text-[26px] text-primary-container" />
              <span className="text-base">{item.label}</span>
            </button>
          ))}
          <button type="button" onClick={onManageWallets} className="flex w-full items-center gap-6 px-6 py-4 text-left hover:bg-surface-container-low">
            <Icon name="account_balance_wallet" className="text-[26px] text-primary-container" />
            <span className="text-base">Gestión de billeteras</span>
          </button>
          <button type="button" onClick={onMica} className="flex w-full items-center gap-6 px-6 py-4 text-left hover:bg-surface-container-low">
            <Icon name="send" className="text-[26px] text-[#229ED9]" />
            <span className="text-base">Mica en Telegram</span>
          </button>
        </div>
        <div className="border-t border-outline-variant/50">
          <button type="button" onClick={logout} className="flex w-full items-center gap-6 px-6 py-4 text-left hover:bg-surface-container-low">
            <Icon name="logout" className="text-[26px] text-primary-container" />
            <span className="text-base">Cerrar sesión</span>
          </button>
        </div>
      </nav>
    </div>
  );
}
