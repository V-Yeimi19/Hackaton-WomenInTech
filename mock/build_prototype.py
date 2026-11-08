"""Une las pantallas exportadas de Stitch en un solo prototipo navegable.

Uso:  python build_prototype.py   ->  genera mock/index.html

Cada pantalla conserva su HTML, estilos y scripts originales. Se renderiza
aislada dentro de un iframe (srcdoc) para que sus IDs y variables globales no
choquen entre sí. El shell (index.html) guarda el estado compartido (saldos,
billeteras, último pago) y conecta los botones de cada pantalla con el resto.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "stitch_remix_of_multi_wallet_yape_app" / "stitch_remix_of_multi_wallet_yape_app"
OUT = ROOT / "index.html"

# nombre de ruta -> carpeta exportada por Stitch
SCREENS = {
    "home": "home_multi_billetera_1",
    "home-nueva": "home_multi_billetera_nueva_billetera_a_adida",
    "yapear": "flujo_yapear_selecci_n_de_billetera",
    "escanear": "esc_ner_qr_visor_y_selector_de_billetera",
    "escanear-foto": "esc_ner_qr_selector_de_billetera",
    "confirmar": "confirmar_monto_pago_qr_multi_billetera",
    "constancia": "constancia_yape_yapeaste",
    "constancia-negocio": "constancia_yape_pago_desde_emprendimiento_caf",
    "te-yapearon": "constancia_de_yapeo_exitoso",
    # "crear" es la pantalla propia screens/crear.html; la de Stitch queda sin enlace.
    "crear-original": "crear_nueva_billetera",
    "desglose": "desglose_de_saldo_consolidado",
    "mi-qr": "mi_qr_por_billetera",
    # Pantallas disponibles por URL (#nombre) pero sin enlace desde Inicio.
    "gestionar": "gestionar_y_ordenar_billeteras",
}


def main() -> None:
    screens = {name: (SRC / folder / "code.html").read_text(encoding="utf-8") for name, folder in SCREENS.items()}
    # Pantallas propias (no exportadas de Stitch): reutilizan el <head> con la config de Tailwind.
    head = screens["home"][: screens["home"].index("<body")]
    for file in sorted((ROOT / "screens").glob("*.html")):
        screens[file.stem] = file.read_text(encoding="utf-8").replace("<!--STITCH_HEAD-->", head)
    # Imágenes locales incrustadas para que index.html siga siendo un solo archivo.
    avatar = "data:image/jpeg;base64," + base64.b64encode((ROOT / "assets" / "mica-avatar.jpg").read_bytes()).decode()
    screens = {k: v.replace("__MICA_AVATAR__", avatar) for k, v in screens.items()}
    template = (ROOT / "prototype_shell.html").read_text(encoding="utf-8")
    payload = json.dumps(screens, ensure_ascii=False).replace("</", "<\\/")
    OUT.write_text(template.replace("/*__SCREENS__*/{}", payload), encoding="utf-8")
    print(f"OK -> {OUT} ({OUT.stat().st_size / 1024:.0f} KB, {len(screens)} pantallas)")


if __name__ == "__main__":
    main()
