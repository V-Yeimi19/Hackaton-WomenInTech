/** Ejemplos orientativos según el rubro declarado, sin clasificar ventas reales. */
export function topSalesSuggestions(business: string): string[] {
  const normalized = business.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  const categories: [RegExp, string[]][] = [
    [/librer|papeler|utiles|libros/, ["Cuadernos", "Útiles escolares", "Libros", "Copias e impresiones"]],
    [/bodega|abarrot|minimarket|almacen/, ["Arroz y abarrotes", "Bebidas", "Golosinas", "Productos de limpieza"]],
    [/cafeter|cafe\b|postre|pasteler|panader/, ["Café y bebidas", "Postres", "Panes y sándwiches", "Desayunos"]],
    [/comida|restaur|menu|cocina|cevich|poller/, ["Menús del día", "Platos a la carta", "Bebidas", "Postres"]],
    [/ropa|calzado|prenda|boutique|zapat/, ["Polos y blusas", "Pantalones", "Zapatos y zapatillas", "Accesorios"]],
    [/salon|barber|peluquer|belleza|unas/, ["Cortes de cabello", "Tintes", "Peinados", "Manicure y pedicure"]],
    [/ferreter|herramient/, ["Herramientas", "Pinturas", "Material eléctrico", "Gasfitería"]],
    [/farmac|botica/, ["Medicamentos", "Cuidado personal", "Vitaminas", "Productos para bebés"]],
    [/fruta|verdura/, ["Frutas de temporada", "Verduras", "Hierbas", "Jugos"]],
    [/tecnolog|celular|comput|electron/, ["Accesorios para celulares", "Cargadores y cables", "Equipos", "Reparaciones"]],
  ];
  return categories.find(([pattern]) => pattern.test(normalized))?.[1]
    ?? ["Productos de uso diario", "Productos por encargo", "Servicios por cita", "Reparaciones y mantenimiento"];
}
