/** Convierte el promedio declarado a un total diario orientativo en céntimos. */
export function dailySalesCents(answer: string): number | null {
  const text = answer.toLowerCase().trim();
  if (/-\s*\d/.test(text) && !/\d\s*[-–]\s*(?:s\s*\/\s*)?\d/.test(text)) return null;
  const numbers = text.match(/\d+(?:[.,]\d+)*/g)?.map((value) => {
    const normalized = value.replace(/[.,](?=\d{3}(?:[.,]|$))/g, "").replace(",", ".");
    return Number(normalized);
  });
  if (!numbers?.length || numbers.length > 2 || numbers.some((value) => !Number.isFinite(value) || value <= 0)) return null;
  let average = numbers[0];
  if (numbers.length === 2) {
    if (numbers[1] < numbers[0]) return null;
    average = (numbers[0] + numbers[1]) / 2;
  } else if (/menos|hasta/.test(text)) average /= 2;
  else if (/m[aá]s de/.test(text)) average *= 1.2;
  const cents = Math.round(average * 100);
  return cents >= 10 && cents <= 100_000_000 ? cents : null;
}

/** Diez cobros distintos que suman exactamente el promedio diario elegido. */
export function demoPayments(totalCents: number) {
  const names = ["Ana", "Rosa", "María", "Carmen", "Lucía", "Elena", "Patricia", "Sofía", "Isabel", "Julia"];
  const weights = [5, 8, 4, 12, 6, 10, 15, 9, 14, 17];
  if (!Number.isSafeInteger(totalCents) || totalCents < names.length) throw new Error("Promedio insuficiente para diez cobros.");
  let remaining = totalCents;
  return names.map((name, index) => {
    const cents = index === names.length - 1 ? remaining : 1 + Math.floor((totalCents - names.length) * weights[index] / 100);
    remaining -= cents;
    return { name, amount: (cents / 100).toFixed(2) };
  });
}
