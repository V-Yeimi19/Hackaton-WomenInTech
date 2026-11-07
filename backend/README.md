# Backend Mica

Implementación de demostración del [README de producto](../README.md). Solo mueve dinero virtual en PEN. La revisión y sus límites están en [AUDIT.md](AUDIT.md).

## Ejecución

Desde la raíz, copiar `.env.example` a `.env`. Con Docker Desktop iniciado:

```powershell
docker compose up --build -d
```

Compose espera PostgreSQL, ejecuta las migraciones y después inicia API y worker. API: `http://localhost:8000/docs`; salud: `/health/live` y `/health/ready`. El worker procesa inbox, outbox y calendario; debe permanecer activo. La imagen contiene el backend y corre como usuario sin privilegios.

Alternativa local, desde `backend`, con Python 3.12 y PostgreSQL:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.lock -e ".[dev]"
$env:DATABASE_URL='postgresql+psycopg://mica:mica@localhost:5432/mica'
python -m alembic upgrade head
uvicorn app.main:app --reload
```

En otra terminal, con el mismo entorno y conexión:

```powershell
python -m app.jobs.worker
```

La configuración carga el `.env` de la raíz y el del directorio actual; las variables de entorno tienen precedencia. HTTPS exige sustituir los cuatro secretos `dev-*` por valores aleatorios independientes de al menos 32 caracteres. `APP_ENV=demo` habilita los escenarios. Los endpoints de simulación de WhatsApp solo funcionan en modo `fake`; no verifican teléfonos reales.

## Pruebas y calidad

Usar una base PostgreSQL exclusiva de pruebas; la suite agrega datos sintéticos y no borra el libro:

```powershell
$env:DATABASE_URL='postgresql+psycopg://mica:mica@localhost:5432/mica_test'
$env:MICA_TEST_DATABASE_URL=$env:DATABASE_URL
python -m alembic upgrade head
python -m ruff check .
python -m mypy app
python -m pytest --cov=app
```

Sin `MICA_TEST_DATABASE_URL`, las pruebas de integración se omiten explícitamente. No interpretar esa ejecución como validación de PostgreSQL. CI utiliza PostgreSQL 17 y ejecuta migraciones, lint, tipos, pruebas, comandos de worker/scheduler y build de imagen. La ejecución local documentada usó PostgreSQL 18.6.

Carga reproducible: `python -m tests.benchmark_backend`. Crea 10 000 movimientos, 20 sesiones, 200 lecturas con 20 lectores concurrentes, 20 persistencias de webhook y 10 reportes. Imprime p95 y configuración. No mide transporte de red ni Twilio.

## Recorrido de API

1. `POST /api/v1/demo/sessions` con `{"scenario":"empty"}`; guardar `session_token`.
2. Usar `Authorization: Bearer <token>` o cookies con `X-CSRF-Token` para escrituras.
3. `POST /api/v1/business/activation` con nombre y `consent_core=true`; WhatsApp e invitaciones son opciones separadas.
4. El `qr_token` abre `POST /api/v1/demo/qr/{token}/sales`, con `{"amount":"200.00"}`.
5. Crear pagos, transferencias y registros de efectivo con una `Idempotency-Key` por comando. Reutilizar la clave al reintentar el mismo cuerpo.
6. `POST /api/v1/reports/preview` con `{"kind":"PRELIMINARY"}`; consultar `/reports`, `/education/recommendation` y `/opportunities/latest`.

También existen escenarios sintéticos `risk` y `stable`. Sus consentimientos y semanas son fixtures de demostración; no prueban decisiones de una persona real. Cada escenario `fake` recibe un teléfono ficticio independiente.

## WhatsApp

`MESSAGING_MODE=fake` no contacta personas. Para probar Twilio, configurar SID, Auth Token, sender y URLs públicas exactas del webhook y callback. Crear un código mediante `/channel-link-challenges` y enviar `VINCULAR <código>` desde el teléfono autorizado en el Sandbox. Los escenarios no verifican automáticamente teléfonos en modo Twilio.

`PROCESS_INBOX_INLINE=false` deja el trabajo al worker. El webhook valida firma/cuenta/destinatario, persiste y responde. La usuaria puede enviar `RESUMEN`, `AYUDA`, `PAUSAR`, `REANUDAR`, `1` o `2`. Fuera de 24 horas se bloquea el texto libre; no se presupone una plantilla aprobada. Un timeout o proceso interrumpido al enviar queda `UNKNOWN` para conciliación manual, sin reenvío ciego. `ACCEPTED` espera callback y nunca se vuelve a enviar automáticamente.

Domingo 20:00 Lima: preliminar. Lunes 00:05: cierre disponible en app, sin segundo mensaje automático. Un evento tardío genera un trabajo de revisión, conservando el snapshot anterior y sin envío adicional.

## Respaldo y operación

Programar diariamente `pg_dump -Fc` con credenciales del entorno; restaurar con `pg_restore --exit-on-error` en una base separada y comparar conteos y versión de Alembic. La programación del respaldo y el hosting son responsabilidad del despliegue. No publicar archivos `.env`, datos de PostgreSQL o respaldos.

Consultar `inbound_events` y `scheduled_jobs` en `DEAD`, mensajes `UNKNOWN` y antigüedad de pendientes desde una conexión de operador; no hay un endpoint público que exponga esos datos. Tras resolver una incidencia, el operador debe conciliar el efecto antes de reintentar. Los logs de aplicación contienen tipo de error, ruta de contrato, latencia y correlación, sin parámetros SQL ni cuerpo financiero. Configurar el servidor/proxy para que tampoco registre URLs con tokens QR o cabeceras de autorización.
