# Revisión técnica del backend

Fecha: 7 de noviembre de 2026. Referencia: README raíz, especificación 2.0. Alcance: backend, persistencia, contratos y preparación de despliegue. No incluye revisión del frontend ni acreditación institucional, legal o ISO.

## Dictamen

El backend implementa el recorrido P0 y cuenta con evidencia automatizada de sus cálculos, persistencia, autorización básica, concurrencia y recuperación. Se corrigieron defectos que impedían considerarlo conforme: fallos del scheduler, reenvíos tras resultados inciertos, reasignación de teléfonos entre escenarios, errores de tipado, reintentos de correcciones y falta de invariantes entre negocios.

**Conformidad técnica condicionada para demostración con datos sintéticos. No se certifica el cierre integral del P0:** faltan el ensayo real del canal, hosting, pruebas móviles/usabilidad y cierre operativo de los puntos descritos abajo. Aprobar pruebas no equivale a certificar cumplimiento universal de estándares de software.

## Evidencia ejecutada

Entorno: Windows 11, Python 3.12.10, PostgreSQL 18.6 local aislado, FastAPI/SQLAlchemy y dependencias del entorno existente. La arquitectura de despliegue y CI selecciona PostgreSQL 17 según el README; esa versión queda para el pipeline. El motor Docker no estaba iniciado y no se ejecutó el build local. El acceso del sandbox a CPU/RAM por WMI estaba restringido; no se dispone de ficha completa de hardware.

| Comprobación | Resultado |
|---|---|
| pytest con PostgreSQL real | 90 pruebas aprobadas |
| Cobertura de líneas de aplicación | 78%, redondeado; no cobertura total de ramas |
| Ruff | Sin errores |
| Mypy | Sin errores en 91 archivos de aplicación |
| Formato Ruff | Aplicado a aplicación, pruebas y migraciones |
| Migración de BD vacía | 0001 → 0002 → 0003 → 0004 aplicada |
| Worker y scheduler, proceso nuevo con `--once` | Ejecutados correctamente contra BD migrada |
| Respaldo y restauración | `pg_dump -Fc` y `pg_restore --exit-on-error` en otra BD |
| Comparación tras restaurar | Coinciden 610 operaciones, 1220 asientos, 98 reportes y 845 eventos de auditoría en el respaldo comprobado |
| Contrato | OpenAPI versionado en `docs/contracts/openapi.json`, con prueba de coincidencia |

Existe una advertencia de deprecación de `BlockingPortal` en la combinación instalada de Starlette/AnyIO; no provoca fallos. Las pruebas de integración se omiten si no se configura `MICA_TEST_DATABASE_URL`; CI sí la configura y usa PostgreSQL real.

Carga reproducible mediante `python -m tests.benchmark_backend`: un proceso de aplicación en TestClient, PostgreSQL local, 10 000 movimientos del negocio evaluado, 20 sesiones, 200 lecturas con 20 lectores concurrentes, 20 webhooks y 10 reportes. Mediciones de la última ejecución:

| Operación | p95 local | Objetivo README |
|---|---:|---:|
| Lectura de saldos | 317.97 ms | <500 ms |
| Persistencia de webhook | 8.26 ms | <2000 ms |
| Reporte de 10 000 movimientos | 538.82 ms | <5000 ms |

Las muestras son acotadas y usan transporte HTTP en proceso. No acreditan rendimiento por Internet, de Twilio, del hosting futuro ni bajo cargas sostenidas. La restauración local acredita el procedimiento y los conteos indicados, no una política de respaldos diarios ya desplegada ni un SLA de RPO/RTO.

## Correspondencia funcional

| Requisitos | Implementación y evidencia |
|---|---|
| RF-01–03 | Sesiones con hash, CSRF, activación con consentimiento y QR opaco. Código de vínculo aleatorio de un solo uso; cuotas de generación y consumo. Canal real pendiente de ensayo autorizado. |
| RF-04–08 | Libro balanceado, procedencia DEMO, cuentas por medio, bloqueo transaccional, idempotencia de comandos/eventos, pagos y efectivo. Integraciones PostgreSQL validan el ejemplo numérico y la concurrencia. |
| RF-09–10 | Clasificación con versión y bloqueo; correcciones por compensación/reemplazo, respuesta idempotente y paginación. Pruebas HTTP y de persistencia. |
| RF-11–12 | Preliminar/cierre, límites Lima, revisiones, calidad, comparación y tres alertas con prioridad. Evento tardío encola revisión sin reemplazar snapshot ni reenviar. |
| RF-13–14 | Inbox/outbox, worker, callbacks, ventana, revocación y preferencias. Timeout queda UNKNOWN; aceptación no se reenvía. Fake y pruebas de firma disponibles; entrega real no acreditada. |
| RF-15 | Reglas de ocho semanas, alertas, consentimientos, deuda y cuota ilustrativa. Una consulta no mantiene invitaciones habilitadas si se revocó consentimiento, desactivaron preferencias o quedó desactualizado el reporte. |
| RF-16 | POST `/usage-events`: catálogo cerrado y rechazo de campos extra; sin importes ni texto libre en analítica. Auditoría mantiene entorno y actor para posteriores métricas. |
| RF-17 | Catálogo determinístico y GET `/education/recommendation`. Sin enlaces institucionales que no hayan sido validados por el equipo. |
| RF-18–19 | P1: voz y exportación no se declaran terminadas. Los adaptadores opcionales permanecen fuera de la entrega mínima. |
| RF-20 | Integraciones bancarias reales fuera de alcance; ninguna se acredita por esta revisión. |

## Trazabilidad de aceptación

| Criterios README | Evidencia principal |
|---|---|
| CA-01, CA-04, CA-06–09, CA-11 | `tests/integration/test_http_flow.py`: recorrido, rechazo sin consentimiento, dinero inválido, clasificación y corrección de otra propietaria. No sustituye un barrido de penetración de todas las rutas. |
| CA-02–03, CA-05, CA-12, CA-23, CA-28 | `test_acceptance.py`: deduplicación en servicio persistente, retiros concurrentes, ejemplo financiero con faltante digital de 1400, compensación e idempotencia. |
| CA-10, CA-24 | `test_http_flow.py`: firma Twilio inválida y evento firmado con procedencia incompatible; errores 403/422 antes de aceptar. |
| CA-13–18, CA-25–26 | Unidades de insights, alertas y oportunidades: denominador cero, reglas de estabilidad/deuda, 20%, prioridad y umbrales estrictos; corte domingo probado además en PostgreSQL. |
| CA-19–22, CA-27 | Integraciones de revocación, ventana, recuperación del inbox, timeout y callbacks fuera de orden. El reinicio real de worker y la prueba de fallos durante entrega externa necesitan ampliar el ensayo operativo. |
| Invariantes adicionales | `test_recovery.py`: no editar importes/asientos, no agregar asientos a una operación anterior, FK entre negocios, cuotas, revisión tardía y deduplicación del calendario. |

Esta tabla relaciona los escenarios con comprobaciones existentes; **no declara ejecutados todos los CA en todos los niveles**. Por ejemplo, la estabilidad se prueba en el dominio, mientras que la concurrencia se prueba en PostgreSQL. El E2E de navegador y el ensayo del teléfono siguen pendientes.

## Cambios de calidad y operación

- Cuatro migraciones controlan balance diferido, aislamiento por negocio, inmutabilidad de asientos/operaciones/snapshots y cuotas compartidas entre procesos.
- La idempotencia reserva la clave con bloqueo de transacción antes de ejecutar el comando. La unicidad externa persiste más allá de la retención de claves HTTP.
- Los escenarios no reasignan teléfonos entre sesiones ni crean vínculos reales en modo Twilio. Los simuladores de WhatsApp se bloquean cuando se configura el canal real.
- El envío se reclama bajo bloqueo; `ACCEPTED`, `UNKNOWN` y estados finales no vuelven a enviarse. Se verifica negocio del vínculo, consentimiento y ventana antes del intento.
- El cierre del lunes no produce un segundo WhatsApp. Los jobs conservan el ID del reporte para no generar una nueva revisión por un reintento del mismo trabajo.
- Se exige zona horaria en DTO temporales e importes dentro de NUMERIC(14,2). El simulador rechaza datos monetarios inválidos antes del inbox.
- HTTPS activa cookies Secure y exige sustituir secretos locales. El modo demo controla la exposición de rutas de simulación.
- Los logs de aplicación registran tipo de error, ruta de contrato, correlación y latencia; evitan serializar excepciones SQL con parámetros sensibles.
- Compose incorpora migración previa a API/worker. Docker excluye entornos, secretos y datos locales, y ejecuta como usuario sin privilegios. Pipeline de CI agregado, todavía no ejecutado en GitHub desde esta sesión.

## Pendientes de cierre de entrega

1. Configurar Twilio Sandbox, HTTPS y teléfono autorizado; verificar vínculo, RESUMEN, callback y revocación con evidencia sin teléfonos completos. No existe envío real acreditado en esta sesión.
2. Ejecutar el pipeline con PostgreSQL 17 y Docker. La validación local utiliza PostgreSQL 18.6; el archivo de CI no es evidencia de una ejecución remota aprobada.
3. Probar frontend con Playwright en móvil, accesibilidad y comprensión de usuarias. Este encargo se trabajó sobre el backend.
4. Provisionar hosting y asignar responsable por 30 días; programar respaldos diarios, monitoreo y alertas de jobs atrasados/DEAD/UNKNOWN; medir RPO/RTO en ese entorno.
5. Definir y ejecutar retención/anonimización de teléfonos y mensajes del ensayo real al concluir las pruebas. Los datos automáticos de esta revisión son sintéticos; la configuración de canal real no constituye por sí sola un piloto apto para datos personales.
6. Revisar editorialmente el contenido educativo y documentar evidencia de usabilidad. Voz, exportación e integraciones reales conservan sus prioridades P1/futura del README.

No se publicaron servicios ni se enviaron mensajes a terceros. Los cambios originales del workspace, incluida la sustitución previa de las carpetas antiguas de backend, se conservaron sin hacer commits ni restauraciones destructivas.
