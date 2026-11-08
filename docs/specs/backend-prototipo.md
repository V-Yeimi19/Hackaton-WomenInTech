# Spec: backend funcional para el prototipo de Mica

> Estado: **implementado F0–F6** (F7 de empalme con el agente: contrato listo) · 2026-11-08
> Objetivo: que `mock/index.html` funcione **igual que antes**, pero contra la API real (FastAPI + PostgreSQL) en lugar de `localStorage`, y dejar el contrato listo para el agente (otra desarrolladora).

## 1. Por qué (criterio del jurado)

**Viabilidad técnica y operativa (40 %)**: funcionalidad real, stack adecuado, escalabilidad potencial y factibilidad a corto plazo.

| Criterio | Cómo se cubre |
|---|---|
| Funcionalidad real | Login, saldos, billeteras, yapeos, QR, transferencias y movimientos persisten en PostgreSQL. Cada jurado entra con su número y ve sus propios datos. |
| Stack adecuado | Se reutiliza lo existente: FastAPI, libro de doble entrada con triggers, idempotencia, Alembic y CI con PostgreSQL. |
| Escalabilidad | Billeteras como entidad (N por usuaria), saldos derivados del libro, paginación por cursor, límites en el servidor y contrato OpenAPI versionado. |
| Factibilidad | Fases cortas con pruebas automáticas: 101 de backend, 23 E2E contra la API real y 41 E2E en modo local. |

## 2. Decisiones aprobadas

1. **Principal = hogar, Emprendimiento = negocio.** Cada billetera tiene su cuenta en el libro:
   - Principal → `HOUSEHOLD_DIGITAL`
   - Emprendimiento → `BUSINESS_DIGITAL`
   - Ahorro y billeteras creadas → `WALLET` (nuevo tipo; varias por negocio)

   Así los reportes negocio/hogar funcionan sin cambios.
2. **Eliminar billetera = archivarla.** El libro es inmutable: sus movimientos se ocultan de las listas pero quedan para auditoría. Si tiene saldo, primero se mueve a otra billetera.
3. **El login crea el vínculo de WhatsApp** (`channel_links`) para que el agente reconozca a la usuaria por su número. Solo en modo `fake`; en Twilio real sigue exigiéndose `VINCULAR <código>`.
4. **Yapeo como operación propia** (`POST /yapeos`); `/payments` no se toca. La categoría alimenta la clasificación existente:
   - *Volver a surtir* y *Local/servicios/ayudantes* → `BUSINESS_PAYMENT`
   - *Para mí o mi familia* → `HOUSEHOLD_WITHDRAWAL`
   - Desde Principal, ahorro u otras billeteras → `PERSONAL_PAYMENT`
5. **Datos aleatorios por número**:
   - La semilla es el hash HMAC del teléfono, así que el mismo número siempre parte de los mismos datos y números distintos reciben datos distintos.
   - Se generan una sola vez, en el primer login: saldos iniciales y 9 movimientos.
6. **Límites en el servidor**: S/ 500 por yapeo y S/ 2,000 diarios en hora de Lima (`PAYMENT_LIMIT_PEN`, `DAILY_LIMIT_PEN`).
7. **Movimientos como vista propia** (`/movements`): `/transactions` sigue siendo la vista contable y no cambia. Cada movimiento trae número de operación (8 dígitos, único por entorno) y código de seguridad, que son los mismos en la constancia, en el detalle y para el agente.

## 3. Contrato de API nuevo (prefijo `/api/v1`)

| Método y ruta | Auth | Cuerpo → respuesta | Errores |
|---|---|---|---|
| `POST /auth/phone-login` | — (solo demo) | `{phone}` → `{session_token, csrf_token, expires_at, user_id, business_id, phone_masked, is_new}` | 422 `INVALID_PHONE`, 429 |
| `POST /auth/logout` | sesión | → 204 (revoca el token) | 401 |
| `GET /me` | sesión | → `{user_id, business_id, phone_masked, environment, session_expires_at}` | 401 |
| `GET /wallets` | negocio | → `{items[{id, name, role, purpose, icon, color, is_primary, is_business, balance}], total}` | — |
| `POST /wallets` | negocio + Idem | `{name, purpose: BUSINESS\|SAVINGS, icon?, color?}` → `Wallet` | 422 `NAME_INVALID`, 409 `NAME_TAKEN`, 409 `WALLET_LIMIT` |
| `DELETE /wallets/{id}?move_to_wallet_id=` | negocio + Idem | → `{archived, moved_amount, hidden_movements}` | 409 `PRIMARY_LOCKED`, 409 `BALANCE_REQUIRES_DESTINATION` |
| `POST /wallet-transfers` | negocio + Idem | `{from_wallet_id, to_wallet_id, amount, note?≤40}` → `{movement, wallets}` | 409 `INSUFFICIENT_BALANCE`, 422 `SAME_WALLET`, 422 `NOTE_TOO_LONG` |
| `POST /yapeos` | negocio + Idem | `{from_wallet_id, amount, counterparty{type: CONTACT\|PHONE\|MERCHANT, name, phone?}, category?, message?}` → `{movement, wallets}` | 409 `INSUFFICIENT_BALANCE`, 422 `PER_PAYMENT_LIMIT`, 422 `DAILY_LIMIT` (`details.remaining`), 422 `CATEGORY_NOT_ALLOWED` |
| `GET /movements?wallet_id=&cursor=&limit=` | negocio | → `{items[Movement], next_cursor}` | — |
| `GET /movements/{id}` | negocio | → `Movement` (datos de la constancia) | 404 |
| `POST /demo/incoming-yapes` | negocio + Idem (solo demo) | `{to_wallet_id, amount, from_name}` → `{movement, wallets}` | — |

`Movement` = `{id, operation_number, security_code, kind, direction: IN|OUT|TRANSFER, title, amount (con signo), occurred_at, wallets[], from_wallet, to_wallet, counterparty_name, counterparty_phone_masked, note, category, category_label}`.

Todos los mensajes de error vienen en español y listos para mostrar; el frontend los muestra tal cual.

## 4. Fases

| Fase | Estado | Entregable |
|---|---|---|
| F0 | ✅ | Contrato (este documento + `docs/contracts/openapi.json` regenerado) |
| F1 | ✅ | Login por teléfono, datos aleatorios, logout y `/me` (`identity`) |
| F2 | ✅ | Billeteras: migración `0005`, `GET/POST /wallets` (`wallets`) |
| F3 | ✅ | Movimientos y constancias: `/movements` y columnas de constancia en `transactions` |
| F4 | ✅ | Yapeos (contacto, celular y QR) con límites y categorías |
| F5 | ✅ | Transferencias y eliminar billetera con traslado de saldo |
| F6 | ✅ | `mock/prototype_shell.html` usa la API si hay backend; sin backend sigue en modo local |
| F7 | 🔜 | Empalme con el agente: usa la misma sesión y endpoints; el vínculo de WhatsApp ya se crea en el login |

## 5. Cómo funciona el frontend con el backend

- **Con backend** (en localhost se detecta solo; en otro dominio se pasa `?api=https://tu-backend`, que se recuerda): `state` es solo una caché. Cada acción llama a la API y refresca billeteras y movimientos desde el servidor.
- **Sin backend** (o con `?api=off`): todo funciona en modo local con `localStorage`, como antes. La demo en Vercel sigue funcionando aunque el VPS no esté arriba.
- **CORS**: `CORS_ORIGINS` incluye `localhost:5500`, `127.0.0.1:5500` y `https://mock-tawny-tau.vercel.app`. En el VPS hay que agregar el dominio final.

## 6. Cómo probar

```bash
# Backend (desde la raíz)
docker compose up --build -d            # aplica la migración 0005

# Pruebas de backend (desde backend/, con una BD de pruebas migrada)
python -m pytest                         # 101 pruebas
python -m ruff check . && python -m mypy app

# E2E del prototipo (desde mock/)
python build_prototype.py
python -m http.server 5500 --bind 127.0.0.1
node tests/e2e-api.mjs                   # contra el backend real
node tests/e2e-local.mjs                 # modo local (sin backend)
```

## 7. Fuera de alcance
Pagos reales o integración con Yape/BCP, clave de 6 dígitos, OTP por SMS, voz y exportación real del QR.

## 8. Pendientes conocidos
- `tests/integration/test_recovery.py::test_channel_link_lookup_is_scoped_to_business` (de main) usa un teléfono fijo: falla si se corre dos veces sobre la misma base. En CI la base es nueva y pasa.
- Inicio muestra una sola billetera creada (el diseño tiene un espacio); el backend admite hasta 5.
- Desglose y Mi QR (pantallas sin enlace) aún muestran datos fijos del diseño.
