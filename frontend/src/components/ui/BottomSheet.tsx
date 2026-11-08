"use client";

import clsx from "clsx";
import { useEffect, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

import { Icon } from "./Icon";

type BottomSheetProps = {
  open: boolean;
  onClose: () => void;
  title?: string;
  eyebrow?: string;
  subtitle?: string;
  children: ReactNode;
  /** Por encima de la barra inferior y del circulito de Mica. */
  className?: string;
};

/** Hoja inferior modal reutilizable: animación, cierre con Esc o tocando fuera, y rol de diálogo. */
export function BottomSheet({ open, onClose, title, eyebrow, subtitle, children, className }: BottomSheetProps) {
  const [mounted, setMounted] = useState(false);
  const [visible, setVisible] = useState(false);

  useEffect(() => setMounted(true), []);
  useEffect(() => {
    if (!open) return setVisible(false);
    const frame = requestAnimationFrame(() => setVisible(true));
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("keydown", onKey);
    };
  }, [open, onClose]);

  if (!mounted || !open) return null;
  return createPortal(
    <div
      className={clsx(
        "fixed inset-0 z-[70] flex items-end justify-center bg-inverse-surface/50 transition-opacity duration-200",
        visible ? "opacity-100" : "opacity-0",
      )}
      onClick={(event) => event.target === event.currentTarget && onClose()}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={clsx(
          "max-h-[88vh] w-full max-w-[430px] overflow-y-auto rounded-t-[28px] bg-surface-container-lowest px-4 pb-6 pt-3 shadow-xl transition-transform duration-300",
          visible ? "translate-y-0" : "translate-y-full",
          className,
        )}
      >
        <div className="mx-auto mb-3 h-1.5 w-10 rounded-full bg-outline-variant" />
        {title && (
          <div className="mb-3 flex items-start justify-between gap-3">
            <div>
              {eyebrow && <p className="text-caption font-bold uppercase tracking-wider text-secondary">{eyebrow}</p>}
              <h2 className="text-title text-on-surface">{title}</h2>
              {subtitle && <p className="text-sm text-on-surface-variant">{subtitle}</p>}
            </div>
            <button
              type="button"
              onClick={onClose}
              aria-label="Cerrar"
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-surface-container-high text-on-surface-variant"
            >
              <Icon name="close" className="text-[20px]" />
            </button>
          </div>
        )}
        {children}
      </div>
    </div>,
    document.body,
  );
}
