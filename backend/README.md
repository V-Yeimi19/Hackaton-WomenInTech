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

## Chat de Mica: app y Telegram

La app y Telegram mantienen conversaciones independientes. Comparten un perfil del
negocio por billetera: rubro, productos más vendidos, ventas diarias declaradas,
gastos fijos y horario preferido. El perfil se guarda en PostgreSQL al responder
cada pregunta en la app. Telegram lo consulta en su siguiente respuesta con IA;
no recibe los mensajes privados del chat web. El horario guardado es una
preferencia; no modifica por sí solo el calendario del scheduler.

Endpoints autenticados con la sesión del negocio:

- `GET /api/v1/agent/profile?wallet_id=<uuid>`: perfil y versión actual (0 si está vacío).
- `PATCH /api/v1/agent/profile`: `{wallet_id, answers, expected_version}`. Hasta cinco
  respuestas de 500 caracteres; una versión desactualizada devuelve 409.
- `POST /api/v1/agent/chat`: `{wallet_id, message, request_id}`. `request_id` es un UUID
  reutilizable al reintentar el mismo mensaje; devuelve `{id, request_id, message, reply, created_at}`.
- `GET /api/v1/agent/chat?wallet_id=<uuid>&limit=50&cursor=<uuid>`: intercambios de la app
  en orden cronológico y `next_cursor` para recuperar los anteriores. No contiene Telegram.

El servidor verifica que la billetera pertenezca al negocio autenticado, sea de
negocio y esté activa. El contexto de IA usa historial del servidor, no el enviado
por el navegador. Las opciones Ayuda, Resumen, Pausar y Reanudar funcionan en ambos
canales; cada respuesta se entrega en el canal donde se consultó. La personalización
local anterior se recupera al abrir el chat si aún no existe perfil en el servidor.

## Confirmación de ingresos y gastos

Un mensaje de la app o una transcripción de Telegram con movimientos realizados
prepara un borrador, nunca un asiento inmediato. Mica extrae hasta seis movimientos,
valida montos en PEN, identifica las billeteras y comprueba que los totales coincidan
con el desglose. Si falta un medio o hay varias billeteras posibles, solicita aclaración.

- **Digital/Yape:** el importe es información de movimientos existentes. No se
  vuelve a abonar ni descontar. La revisión muestra discrepancias con el total digital
  registrado para la fecha; confirmar no altera ese saldo.
- **Efectivo:** se añade como ingreso/gasto de la billetera indicada después de
  confirmar. Si no hay efectivo inicial, Mica pregunta cuánto había **antes** de esos
  movimientos. Ese importe no cuenta como venta. El efectivo legado sin billetera
  se conserva y se reasigna a billeteras de negocio hasta el importe inicial declarado,
  sin duplicarlo ni mezclarlo con el efectivo personal.
- **Confirmar / Editar / Cancelar:** botones en ambos chats y opciones escritas.
  Editar solicita el reporte completo corregido; cancelar no registra movimientos.
  Los botones llevan identificador y versión. Un botón viejo, otra cuenta o una
  confirmación repetida no vuelve a registrar el lote. El borrador vence en 30 minutos.

La confirmación bloquea las cuentas y valida todos los saldos antes de publicar un
lote atómico. El negocio, el hogar y cada billetera conservan efectivo independiente;
los reportes del negocio excluyen el efectivo personal. Si cambian los saldos desde
la revisión, se exige una nueva confirmación. Los movimientos confirmados mantienen
las protecciones de inmutabilidad del libro.

`POST /api/v1/agent/chat` acepta opcionalmente `declaration_action={id, version, action}`
(`confirm`, `edit`, `cancel`) y devuelve `declaration` con el estado y las acciones
disponibles. `GET /api/v1/agent/declarations?wallet_id=<uuid>` recupera el borrador
de la app y los últimos hechos financieros confirmados, compartidos entre canales;
no expone los textos privados de la conversación de Telegram.

En `GET /wallets`, `balance` sigue siendo digital; `cash_balance=null` indica que
falta preguntar el efectivo inicial. `combined_balance` suma ambos por billetera.
`cash_total` suma efectivo asignado; `unallocated_cash` conserva efectivo legado;
`combined_total` incluye digital, efectivo asignado y legado. `GET /movements`
incluye `medium=DIGITAL|CASH` y permite filtrar ambos medios por billetera.

## Audios de Telegram

Mica acepta notas de voz, audios y documentos con MIME `audio/*` de cuentas ya
vinculadas. Descarga el archivo en memoria y lo transcribe mediante
[Groq Speech to Text](https://console.groq.com/docs/speech-to-text), usando la
misma `GROQ_API_KEY` de las consultas. La respuesta se entrega como texto en
Telegram, con el perfil compartido del negocio y el historial propio de ese canal.

`ENABLE_TELEGRAM_AUDIO=true` y `ENABLE_LLM=true` habilitan el recorrido. El modelo
de transcripción predeterminado es `GROQ_TRANSCRIPTION_MODEL=whisper-large-v3-turbo`.
Los límites son `TELEGRAM_AUDIO_MAX_BYTES=10000000` (10 MB) y
`TELEGRAM_AUDIO_MAX_SECONDS=180` (3 minutos); se pueden reducir. La descarga también
verifica el tamaño real del contenido para archivos sin tamaño declarado. No se
guardan archivos de audio locales: únicamente su transcripción en `inbound_events.transcript`,
separada del payload original para conservar la deduplicación de Telegram.

Si el audio excede los límites, no se puede descargar o transcribir, o la función
está apagada, Mica envía una explicación y permite continuar por texto. Los audios
de chats sin vincular no se descargan ni se envían a Groq. WhatsApp y la respuesta
por voz no forman parte de esta integración.

Documentación de descarga: [Telegram getFile](https://core.telegram.org/bots/api#getfile).

## WhatsApp

`MESSAGING_MODE=fake` no contacta personas. Para probar Twilio, configurar SID, Auth Token, sender y URLs públicas exactas del webhook y callback. Crear un código mediante `/channel-link-challenges` y enviar `VINCULAR <código>` desde el teléfono autorizado en el Sandbox. Los escenarios no verifican automáticamente teléfonos en modo Twilio.

`PROCESS_INBOX_INLINE=false` deja el trabajo al worker. El webhook valida firma/cuenta/destinatario, persiste y responde. La usuaria puede enviar `RESUMEN`, `AYUDA`, `PAUSAR`, `REANUDAR`, `1` o `2`. Fuera de 24 horas se bloquea el texto libre; no se presupone una plantilla aprobada. Un timeout o proceso interrumpido al enviar queda `UNKNOWN` para conciliación manual, sin reenvío ciego. `ACCEPTED` espera callback y nunca se vuelve a enviar automáticamente.

Domingo 20:00 Lima: preliminar. Lunes 00:05: cierre disponible en app, sin segundo mensaje automático. Un evento tardío genera un trabajo de revisión, conservando el snapshot anterior y sin envío adicional.

## Respaldo y operación

Programar diariamente `pg_dump -Fc` con credenciales del entorno; restaurar con `pg_restore --exit-on-error` en una base separada y comparar conteos y versión de Alembic. La programación del respaldo y el hosting son responsabilidad del despliegue. No publicar archivos `.env`, datos de PostgreSQL o respaldos.

Consultar `inbound_events` y `scheduled_jobs` en `DEAD`, mensajes `UNKNOWN` y antigüedad de pendientes desde una conexión de operador; no hay un endpoint público que exponga esos datos. Tras resolver una incidencia, el operador debe conciliar el efecto antes de reintentar. Los logs de aplicación contienen tipo de error, ruta de contrato, latencia y correlación, sin parámetros SQL ni cuerpo financiero. Configurar el servidor/proxy para que tampoco registre URLs con tokens QR o cabeceras de autorización.


## Dashboard PDF por Telegram

Desde un chat privado vinculado, pedir `PDF de este mes`, `PDF de hoy`,
`PDF de la semana pasada` o `PDF del 01/10/2026 al 31/10/2026`.
Sin periodo, Mica pregunta; con varias billeteras de negocio, pregunta cu?l,
o acepta `todos mis negocios`. Las fechas son inclusivas y se interpretan en
America/Lima; no se admiten fechas futuras ni rangos superiores a 366 d?as.
La selecci?n pendiente vence a los 30 minutos y admite `Cancelar`.

El PDF de una p?gina contiene ingresos, egresos, resultado (no utilidad contable),
gr?fico por fecha y separaci?n efectivo/digital. Excluye aperturas, movimientos
entre billeteras y gastos personales. El efectivo ya confirmado se lee del libro,
sin sumar su declaraci?n otra vez. Para cada billetera, fecha y direcci?n digital,
el libro tiene prioridad; donde no existen registros, se usa la ?ltima declaraci?n
confirmada del d?a. Las declaraciones sucesivas del mismo total diario se sustituyen,
no se acumulan. Este criterio se explica en el pie del PDF; no supone conciliaci?n
bancaria ni modifica saldos.

El snapshot JSON queda en `outbound_messages.document`; ReportLab lo convierte en
PDF en memoria y Telegram lo recibe por `sendDocument` multipart, sin enlaces
p?blicos. Se conserva la deduplicaci?n del inbox/outbox y no se reenv?a ciegamente
un documento cuya entrega qued? UNKNOWN. La app orienta a continuar en Telegram;
no hay un endpoint de descarga p?blica. Migraci?n: `0010_telegram_dashboard`.

Los controles de declaraciones incluyen Confirmar, Editar y Cancelar incluso si
falta el efectivo inicial: Confirmar solicita el dato pendiente y no publica
movimientos incompletos. La cabecera de la app permanece fija al desplazarse.


## Contexto de movimientos para Mica

La app y Telegram consultan las notas, descripciones, destinatarios y categor?as
RESTOCK / LOCAL_SERVICES / FAMILY guardadas al yapear o transferir. La b?squeda
por concepto tambi?n recorre el historial anterior a los ?ltimos 15 movimientos,
con filtros de periodo interpretados en America/Lima y sin mezclar cuentas.
En la app se limita a la billetera seleccionada; Telegram consulta las billeteras
activas de la cuenta vinculada. No requiere migraci?n ni nuevos datos del usuario.

Los totales de coincidencias se calculan en el backend sobre todas las p?ginas;
el detalle enviado al LLM se limita a 20 movimientos. Las transferencias propias
se presentan por separado, sin sumarlas a ingresos o gastos. Los textos guardados
son datos: no constituyen instrucciones ni prueban un producto espec?fico cuando
solo se eligi? una categor?a general. No se env?an c?digos de seguridad ni tel?fonos.


Si se solicitan varias billeteras, el PDF abre con un resumen general y agrega
una p?gina por billetera con los mismos indicadores, gr?fico por fecha y gr?fico
de efectivo/digital. Los desgloses y el total general se calculan sobre los mismos
movimientos deduplicados, sin volver a consultar ni sumar transferencias internas.
Una sola billetera conserva una sola p?gina. Se acepta pedir expl?citamente
negocio y cuenta personal (Principal), o varios negocios por nombre. El snapshot
conserva los desgloses en `wallet_reports`; no se requiere otra migraci?n.


`PDF de todas mis billeteras de los ?ltimos dos d?as` selecciona todas las
billeteras activas propias: principal, negocios y ahorro, incluso si alguna no
registra ingresos o egresos. La selecci?n se conserva si Mica pregunta el periodo.
`Todos mis negocios` mantiene su alcance limitado a negocios.

Los importes declarados admiten palabras, por ejemplo `gast? veinte soles en
efectivo por dos sacos de az?car`; Mica conserva el concepto y pide confirmaci?n
antes de registrar S/ 20. Las cantidades de productos no se usan como importe.
En consultas de movimientos, `dos sacos de az?car` y `2 sacos de az?car` se buscan
como conceptos equivalentes y se distinguen de `20 sacos` y de un periodo temporal.
