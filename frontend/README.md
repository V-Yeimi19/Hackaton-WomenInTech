# Mica · Frontend (Next.js)

App web de **Mica · Mi Negocio**: billeteras para separar la plata del negocio y de la casa, yapeos, pago con QR, transferencias y constancias. Consume el backend FastAPI del repositorio (`backend/`).

## Stack

| Pieza | Elección | Por qué |
|---|---|---|
| Framework | **Next.js 15 (App Router) + React 19** | Rutas por archivo, Server Components y Route Handlers para el BFF |
| Lenguaje | **TypeScript estricto** | Tipos de punta a punta |
| Estilos | **Tailwind CSS 4** con tokens propios (`globals.css`) | Mismo sistema de diseño que el prototipo |
| Datos del servidor | **TanStack Query** | Caché, estados de carga/error e invalidación tras cada operación |
| Contrato | **openapi-typescript** sobre `docs/contracts/openapi.json` | Si el backend cambia un campo, TypeScript lo detecta |
| Validación | **Zod** en el BFF y reglas puras en `features/*/model.ts` | Respuesta inmediata en el cliente; el backend es la fuente de verdad |
| Pruebas | **Vitest** (unitarias) + **Playwright** (E2E contra el backend real) | |

## Arquitectura

```
Navegador ──► Next.js (BFF) ──► FastAPI ──► PostgreSQL
              │  /api/auth/login   → crea la sesión y guarda el token en cookie httpOnly
              │  /api/auth/logout  → revoca la sesión y borra la cookie
              │  /api/backend/*    → proxy con lista blanca; agrega Authorization desde la cookie
              └  middleware.ts     → sin sesión redirige a /login
```

- **Patrón BFF (Backend for Frontend):** el token nunca llega al JavaScript del navegador (cookie `httpOnly`, `SameSite=Lax`, `Secure` en producción). Tampoco hace falta CORS: el navegador solo habla con su propio dominio.
- **Idempotencia:** toda operación con dinero envía `Idempotency-Key` (`lib/api/http.ts`), así que un reintento no cobra dos veces.
- **Organización por funcionalidad:** cada carpeta de `features/` tiene sus hooks de datos (`api.ts`), su lógica pura (`model.ts`) y sus componentes.

```
src/
  app/                    Rutas: /login, /, /yapear, /escanear, /constancia/[id], /billeteras/nueva, api/*
  components/             UI reutilizable (BottomSheet, Icon, Toast, Skeleton) y Providers
  features/
    auth/                 Login por número
    home/                 Inicio: cabecera, menú lateral, barra inferior
    wallets/              Billeteras: tarjeta, selector, eliminar, transferir, QR, crear
    movements/            Movimientos plegables con filtros y detalle
    yapeo/                Pantalla de monto, teclado, contactos, escáner
    receipts/             Constancias
  lib/
    api/                  Cliente HTTP, tipos generados del OpenAPI y claves de caché
    server/               Código solo de servidor (BFF)
    format.ts             Formatos de dinero y fechas
```

## Cómo correrlo

```bash
# 1. Backend (desde la raíz del repo)
docker compose up --build -d

# 2. Frontend
cd frontend
cp .env.example .env.local      # MICA_API_URL=http://localhost:8000
npm install
npm run dev                     # http://localhost:3000
```

| Script | Qué hace |
|---|---|
| `npm run dev` / `build` / `start` | Desarrollo, build de producción y servidor |
| `npm run lint` · `npm run typecheck` | ESLint y TypeScript |
| `npm test` | Pruebas unitarias (Vitest) |
| `npm run test:e2e` | E2E con Playwright contra el backend real (usa Edge instalado; `PW_CHANNEL=chrome` para Chrome) |
| `npm run api:types` | Regenera los tipos desde `docs/contracts/openapi.json` |

## Despliegue

- **Vercel** (u otro hosting de Next): definir `MICA_API_URL` con la URL pública del backend.
- **Backend:** no hace falta agregar el dominio del frontend a CORS, porque las llamadas salen del servidor de Next.
