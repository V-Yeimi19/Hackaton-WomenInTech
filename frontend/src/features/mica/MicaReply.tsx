"use client";

import Markdown, { type Components } from "react-markdown";

import { splitOptions } from "./reply-options";

/** Solo formato básico: negritas, cursivas y listas. Nada de enlaces, imágenes ni HTML. */
const COMPONENTS: Components = {
  p: ({ children }) => <p className="[&:not(:first-child)]:mt-2">{children}</p>,
  strong: ({ children }) => <strong className="font-bold text-primary-container">{children}</strong>,
  em: ({ children }) => <em className="italic">{children}</em>,
  ul: ({ children }) => <ul className="mt-2 space-y-1">{children}</ul>,
  ol: ({ children }) => <ul className="mt-2 space-y-1">{children}</ul>,
  li: ({ children }) => (
    <li className="flex gap-2">
      <span aria-hidden="true" className="mt-[9px] h-1.5 w-1.5 shrink-0 rounded-full bg-secondary" />
      <span className="min-w-0">{children}</span>
    </li>
  ),
  // La cita (">") es la tarjeta del resumen: recuadro redondeado con una línea por dato.
  blockquote: ({ children }) => (
    <div className="mt-3 space-y-3 rounded-[24px] border border-outline-variant/60 bg-surface-container-lowest px-4 py-4 text-[15px] leading-6 shadow-sm [&_p]:mt-0">
      {children}
    </div>
  ),
  a: ({ children }) => <span>{children}</span>,
  img: () => null,
  h1: ({ children }) => <p className="font-bold">{children}</p>,
  h2: ({ children }) => <p className="font-bold">{children}</p>,
  h3: ({ children }) => <p className="font-bold">{children}</p>,
  code: ({ children }) => <span className="font-semibold">{children}</span>,
};

type MicaReplyProps = {
  content: string;
  /** Al tocar una opción se envía como si la usuaria la escribiera. */
  onOption?: (option: string) => void;
  disabled?: boolean;
};

/** Respuesta de Mica con formato (Markdown) y sus opciones como botones. */
export function MicaReply({ content, onOption, disabled }: MicaReplyProps) {
  const { text, options } = splitOptions(content);
  return (
    <div data-testid="mica-reply">
      <Markdown components={COMPONENTS} skipHtml>{text}</Markdown>
      {options.length > 0 && onOption && (
        <div className="mt-3 flex flex-wrap gap-2" aria-label="Opciones">
          {options.map((option) => (
            <button key={option} type="button" disabled={disabled} onClick={() => onOption(option)}
              className="rounded-full bg-secondary-container px-3 py-1.5 text-xs font-bold text-on-secondary-container active:scale-95 disabled:opacity-50">
              {option}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
