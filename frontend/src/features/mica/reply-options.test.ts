import { describe, expect, it } from "vitest";

import { splitOptions } from "./reply-options";

describe("splitOptions", () => {
  it("separa la línea final de opciones", () => {
    expect(splitOptions("Hoy vendiste **S/ 100.00**.\nOpciones: Resumen, Pausar, Ayuda")).toEqual({
      text: "Hoy vendiste **S/ 100.00**.",
      options: ["Resumen", "Pausar", "Ayuda"],
    });
  });

  it("acepta opciones pegadas al final del párrafo, como en respuestas antiguas", () => {
    expect(splitOptions("Tu saldo digital actual es S/ 4,333.60. opciones: Resumen, Pausar, Reanudar, Ayuda.")).toEqual({
      text: "Tu saldo digital actual es S/ 4,333.60.",
      options: ["Resumen", "Pausar", "Reanudar", "Ayuda"],
    });
  });

  it("entiende 'y' como separador y quita formato", () => {
    expect(splitOptions("Listo.\n**Opciones:** Resumen y Ayuda").options).toEqual(["Resumen", "Ayuda"]);
  });

  it("no toca respuestas sin opciones", () => {
    const text = "Tus opciones son ahorrar más o vender más.";
    expect(splitOptions(text)).toEqual({ text, options: [] });
  });
});
