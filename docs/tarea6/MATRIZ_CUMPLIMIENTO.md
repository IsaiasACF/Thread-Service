# Matriz de cumplimiento — integración final

Revisión inicial sobre `fd3bb278c1e840406432e85c55e379ebec185c74`.
Fuente normativa: [Unidad 6, sección Tarea](https://github.com/rmasad/microservicios/blob/main/06_Interfaz/README.md), revisada el 2026-11-09.
El enunciado exige interfaz web/móvil, integración con microservicios de otros
equipos mediante API Gateway, lectura/escritura, red Compose `microsvcs`, video de
todas las funcionalidades y repositorios públicos. No exige Kubernetes,
autenticación con contraseña, WebSockets, edición ni bot opcional.

Esta matriz distingue evidencia previa de A/B de la validación conjunta de esta
rama. Los estados iniciales no afirman que una prueba nueva ya haya pasado.

| Requisito | Implementación existente | Evidencia previa | Brecha al iniciar esta etapa |
|---|---|---|---|
| Interfaz web utilizable | React/TypeScript/Vite | CHAT_FRONTEND, UI_COMPARTIDA | Repetir contra stack unificado |
| Gateway conecta microservicios | FastAPI/Ariadne, clientes REST por dominio | CHAT_GATEWAY, INTEGRALES_POLLS_B | Verificar seis URLs desde contenedor |
| Lectura y escritura | Contrato GraphQL v1 y hooks Query | Suites A/B y browser-report anteriores | E2E conjunto sin mocks |
| Red `microsvcs` | Compose A/B | Validación estática A y Docker B | Arranque único reproducible |
| Servicios de otros equipos | Integrales y Polls externos | Revisiones en polls-integrals.sources.json | Descarga/verificación automática, sin rutas personales |
| Chat original y corregido | prepare.py, apply_test_patch.py | CHAT_E2E_FINAL | Conservar ambos modos en la integración completa |
| Identidad: crear/recuperar/cambiar/cerrar | IdentityProvider, IdentityPage | Pruebas A y E2E A | Revalidar después de cambios compartidos |
| Canales: crear/listar/buscar/seleccionar | Workspace | Tests A y UI_COMPARTIDA | Recorrido real conjunto |
| Mensajes: enviar/leer/actualizar/autores/fechas | ChatPage, Composer, Author | E2E A/B | Repetir y comprobar relaciones |
| Threads: abrir/publicar/leer/cerrar/recargar | ThreadsPanel y worker | E2E A/B | Repetir en la interfaz compartida |
| Integral correcta y resultado numérico | IntegralsPage, IntegralResult | E2E B, resultado 1/3 | Repetir con fuentes fijadas |
| Integral fallida como dominio | Estado failed/NOT_AN_INTEGRAL | E2E B | Repetir sin ocultar el fallo |
| Historial/filtros/paginación/detalle | Hooks y páginas de Integrales | Tests B y navegador B | Verificar paginación real |
| Encuesta y anuncio | CreatePollForm → Polls → Messages | E2E B y recovery-report | Verificar mismo Messages/IDs y anuncio único |
| Idempotencia | Header del cliente y clave del formulario | Tests B y recovery-report | Repetir éxito/conflicto reales |
| Voto/resultados/duplicado | PollPage y votePoll | E2E B | Repetir con dos usuarios |
| Cierre/autorización/voto cerrado | closePoll y estados de UI | E2E B | Repetir rechazos reales |
| pending_announcement y recuperación | Polls externo y polling UI | recovery-report B | Detener solo Messages propio |
| Navegación/layout/tema | Workspace, ThemeToggle, tokens | UI_COMPARTIDA | Regresión de A y B conjuntamente |
| Claro/oscuro/sistema/persistencia | thread.theme.v1 | Tests de tema y Chromium B | Repetir en nuevo origen |
| Responsive/menú/búsqueda/copiar | Componentes compartidos | ui-theme-check.cjs | Repetir escritorio/móvil/teclado |
| Datos del navegador solo `/graphql` | Cliente único y proxy Vite | Network A/B | Inspección nueva sin interceptores |
| Sin POST automáticos repetidos | Mutaciones retry:false | Tests A/B | Conteos y timeout real controlado |
| Persistencia MongoDB/PostgreSQL | Volúmenes Compose | A en procesos; B en Docker | Reiniciar apps y todas las bases propias |
| Aislamiento de fallos | Clientes por servicio | Tests y recuperación B | Polls caído con Chat; Integrales caído con Threads |
| Contrato v1 intacto | SDL y snapshot independiente | 323 tests Gateway en PR #9 | Ejecutar regresión y revisar diff |
| Regresión React/Thread/offline | Vitest/pytest/validador k8s | Suites de PR #8/#9 | Ejecutar todas tras unificación |
| Sin secretos/fuentes vendorizadas | .gitignore, estado privado | Revisiones A/B | Revisión final de archivos/evidencias |
| Instrucciones para el profesor | Guías por etapa | Documentación previa | ENTREGA_FINAL con comandos únicos |
| Video de todas las funcionalidades | Evidencias interactivas parciales | Capturas y reportes A/B | Guion y, si es posible, grabación real; falta entrega pública del video |
| Repositorios públicos | Thread-Service y repos externos | Enlaces de las guías | Confirmar visibilidad y fijar URLs |
| Kubernetes | Manifiestos anteriores | Pruebas offline | Fuera de alcance; no condiciona entrega U6 |

La evaluación final y enlaces a la evidencia nueva se completarán al finalizar
las pruebas; un video sin publicar no se considerará entregado.

## Resultado final de esta rama

La integración técnica quedó comprobada en Docker real (Engine 28.4.0, Compose
2.39.2). Las brechas iniciales se resuelven así:

| Requisitos agrupados de la matriz inicial | Estado observado | Evidencia nueva |
|---|---|---|
| Interfaz/Gateway/lectura/escritura/seis APIs | Cumple | browser-report.json y gateway-connectivity.json |
| Red microsvcs/arranque único/fuentes externas fijadas | Cumple | integration/final, sources.lock.json y metadatos de 19 servicios |
| Chat original vs copia corregida | Ambas variantes preservadas; tres 500 originales reproducidos | original-docker-report.json; ver advertencia de ENTREGA_FINAL |
| Identidad/canales/mensajes/Threads/recarga | Cumple con servicios reales después del PR #9 | browser-report.json, readBack y capturas 01/10 |
| Integral definida/numérico/fallo/historial/filtros/paginación/detalle | Cumple | browser-report.json y persistence-report.json |
| Integral indefinida y + C en interfaz | Cumple | ui/report.json, indefiniteIntegral |
| Polls/anuncio/idempotencia/voto/cierre/rechazos/pendientes | Cumple | browser-report.json y recovery-report.json |
| Layout/temas/sistema/móvil/menú/búsqueda/copia/teclado | Cumple; 13 capturas, sin overflow/consola | ui/report.json |
| Solo /graphql, IDs de APIs, sin mocks ni retries de POST | Cumple en E2E normal; un POST en timeout real | mutationCounts y recovery-report.json |
| Persistencia de ambas identidades y todos los dominios | Cumple: seis bases y nueve apps reiniciadas | persistence-report.json y application-restart-proof.json |
| Aislamiento ante caídas/recuperación Gateway | Cumple | recovery-report.json y consultas después del reinicio |
| Regresión/snapshot/offline/build/Compose | Cumple: 550 aprobadas, 0 fallidas, 0 omitidas | validation.json; checks CI complementarios |
| Código público/sin alteraciones externas/secretos | Verificado | public-repositories.json; hashes antes/después; revisión de diff |
| Instrucciones y guion | Listos | ENTREGA_FINAL.md y GUIÓN_VIDEO.md |
| Video de todas las funcionalidades | **Pendiente de publicación/enlace académico** | Dos grabaciones Chromium reales locales, decodificadas, sin narración; video-validation.json |
| Kubernetes | No exigido por el enunciado y no ejecutado | Solo tests y validador offline |

Los informes anteriores se encuentran en
[evidencia_integracion_final](evidencia_integracion_final), sin reemplazar los de
PR #7/#8/#9. Las pruebas unitarias con mocks se distinguen del recorrido real.

**Evaluación de entrega:** la integración técnica y la documentación están
listas; la entrega académica no está cerrada hasta publicar/adjuntar el video y
comprobar su acceso. No hay un despliegue compartido docente corregido: el éxito
normal utiliza las tres copias locales explícitas. El nuevo PR queda sin merge.
