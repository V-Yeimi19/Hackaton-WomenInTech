/** Formatos de dinero y fechas (puros, sin dependencias de React). */

const money = new Intl.NumberFormat("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export const MASK = "****";

/** "1820.5" -> "1,820.50" */
export function formatMoney(value: number | string): string {
  return money.format(Math.abs(Number(value)));
}

/** "-12.05" -> "- S/ 12.05" ; "45" -> "S/ 45.00" */
export function formatSigned(value: number | string): string {
  const n = Number(value);
  return `${n < 0 ? "- " : ""}S/ ${formatMoney(n)}`;
}

/** Monto corto para la constancia: 25 -> "25", 12.5 -> "12.50". */
export function formatShort(value: number | string): string {
  const n = Math.abs(Number(value));
  return Number.isInteger(n) ? String(n) : n.toFixed(2);
}

const MONTHS = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Set", "Oct", "Nov", "Dic"];

function time12(date: Date): string {
  const h = date.getHours();
  const m = String(date.getMinutes()).padStart(2, "0");
  return `${((h + 11) % 12) + 1}:${m} ${h < 12 ? "am" : "pm"}`;
}

/** "Hoy - 3:42 pm", "Ayer - 7:20 pm" o "12 May. - 10:00 am". */
export function whenLabel(iso: string, now: Date = new Date()): string {
  const date = new Date(iso);
  const startOfDay = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const days = Math.round((startOfDay(now) - startOfDay(date)) / 86_400_000);
  const day = days === 0 ? "Hoy" : days === 1 ? "Ayer" : `${date.getDate()} ${MONTHS[date.getMonth()]}.`;
  return `${day} - ${time12(date)}`;
}

/** Fecha y hora para la constancia: { date: "08 nov. 2026", time: "11:02 p. m." }. */
export function receiptDate(iso: string): { date: string; time: string } {
  const d = new Date(iso);
  return {
    date: d.toLocaleDateString("es-PE", { day: "2-digit", month: "short", year: "numeric" }).replace(/ de /g, " "),
    time: d.toLocaleTimeString("es-PE", { hour: "2-digit", minute: "2-digit", hour12: true }),
  };
}

/** Formatea un celular mientras se escribe: "987654321" -> "987 654 321". */
export function formatPhoneInput(raw: string): string {
  const digits = raw.replace(/\D/g, "").slice(0, 9);
  return [digits.slice(0, 3), digits.slice(3, 6), digits.slice(6, 9)].filter(Boolean).join(" ");
}

export const isPeruMobile = (raw: string) => /^9\d{8}$/.test(raw.replace(/\D/g, ""));
