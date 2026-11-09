/**
 * Separa la línea "Opciones: Resumen, Pausar, Ayuda" del final de una respuesta de Mica
 * para mostrarla como botones. Acepta también que venga pegada al último párrafo
 * ("… S/ 4,333.60. opciones: Resumen, Ayuda.") como en respuestas anteriores.
 */
const OPTIONS_TAIL = /(?:^|\s)(?:\*\*)?opciones(?:\*\*)?\s*:\s*(?:\*\*)?([^\n]+?)(?:\*\*)?\.?\s*$/i;

export function splitOptions(content: string): { text: string; options: string[] } {
  const match = OPTIONS_TAIL.exec(content);
  if (!match) return { text: content, options: [] };
  const options = match[1]
    .split(/\s*(?:,|\by\b|\bo\b|·|\|)\s*/i)
    .map((option) => option.replace(/[*_`"«»]/g, "").trim())
    .filter((option) => option.length > 0 && option.length <= 30);
  if (options.length === 0 || options.length > 6) return { text: content, options: [] };
  return { text: content.slice(0, match.index).trimEnd(), options: [...new Set(options)] };
}
