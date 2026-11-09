# Verificación local de los workflows

Se ejecutaron las comprobaciones de `.github/workflows/backend.yml` y
`.github/workflows/frontend.yml` sobre el árbol de trabajo actual, en contenedores
Linux y con instalaciones limpias, antes de publicar el commit. Esto no es una
ejecución de GitHub Actions; su resultado se consulta por separado tras el push.

| Comprobación | Resultado |
| --- | --- |
| Backend: Python 3.12, dependencias runtime y extras dev | OK |
| Ruff check y formato | OK, 150 archivos con formato correcto |
| mypy | OK, 109 archivos de código |
| Alembic desde base vacía en PostgreSQL 17 | OK, hasta 0010_telegram_dashboard |
| pytest, integración, contrato y cobertura | 305 pruebas aprobadas; 86 % de cobertura |
| Worker --once | OK |
| Scheduler --once | OK |
| docker build -t mica-backend:ci | OK |
| Frontend: Node 22.23.4, npm ci | OK |
| Tipos API regenerados frente al árbol actual | Coinciden; comparación normalizando CRLF/LF |
| ESLint | OK |
| TypeScript | OK |
| Vitest | 42 pruebas aprobadas |
| Next.js build de producción | OK |

Se corrigió la precondición de `test_ca10_invalid_twilio_signature_is_forbidden`:
la prueba habilita explícitamente el canal cuya firma verifica, sin depender de
la configuración local. No cambia la configuración del producto.

Los scripts usados para las instalaciones limpias están en
`verify-backend-ci.sh` y `verify-frontend-ci.sh`, junto a este informe. Requieren
los montajes y una base de pruebas aislada; no deben apuntarse a producción.
