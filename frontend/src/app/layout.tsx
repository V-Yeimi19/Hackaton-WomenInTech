import type { Metadata, Viewport } from "next";
import { Plus_Jakarta_Sans } from "next/font/google";

import { Providers } from "@/components/providers";

import "./globals.css";

const jakarta = Plus_Jakarta_Sans({ subsets: ["latin"], variable: "--font-jakarta", display: "swap" });

export const metadata: Metadata = {
  title: "Mica · Mi Negocio",
  description: "Separa la plata de tu negocio y de tu casa. Demo del Hackatón Women in Tech 2026.",
  robots: { index: false },
};

export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#742284" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es" className={jakarta.variable}>
      <head>
        {/* eslint-disable-next-line @next/next/no-page-custom-font -- íconos, no tipografía de texto */}
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&display=swap"
        />
      </head>
      <body>
        <Providers>
          {/* Contenedor de ancho de celular: en escritorio se centra. */}
          <div className="relative mx-auto min-h-dvh w-full max-w-[430px] overflow-x-hidden bg-surface shadow-[0_0_60px_rgba(89,0,106,0.12)]">
            {children}
          </div>
        </Providers>
      </body>
    </html>
  );
}
