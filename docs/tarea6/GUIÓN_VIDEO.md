# Guion del video — Tarea 6

Duración objetivo: **7–8 minutos**. Dos integrantes, una demostración real del
mismo stack; no usar capturas estáticas como si fueran operaciones. Mostrar
confirmaciones, resultados y recarga. Hablar con frases cortas mientras se actúa.

## Preparación fuera de cámara

1. Seguir [ENTREGA_FINAL.md](ENTREGA_FINAL.md). Conservar `FINAL_STACK_DIR` y el env
   privado. Levantar el modo **corrected**, con las tres copias docentes de prueba
   explícitas. No usar el clúster ni servicios de terceros.
2. Ejecutar el E2E una vez para disponer de al menos 21 registros de historial
   reales y comprobar los servicios. Esos cálculos son datos sintéticos de prueba.
3. Abrir http://127.0.0.1:15173 en dos perfiles/contextos de navegador. Preparar
   nombres nuevos `Entrega A <hora>` y `Entrega B <hora>`, canal `entrega-<hora>`,
   mensaje `Mensaje de la demostración` y respuesta `Respuesta del hilo`.
4. Preparar estas entradas: `\int_0^1 x^2 \, dx`, `\int x \, dx` y `x + 1`.
   Encuesta: `¿Qué tema revisamos?`, opciones `Chat`, `Integrales`, `Encuestas`,
   duración 15 minutos. Guardar IDs solo desde respuestas/controles de copiar.
5. Abrir la guía con el diagrama y una terminal con
   `python3 integration/final/run.py --directory "$FINAL_STACK_DIR" ps`.
   No mostrar compose.env, contraseñas, inspect completo ni logs con variables.
6. Abrir DevTools Network filtrado por `graphql`; ocultar paneles que dificulten
   leer los formularios. Preparar modo responsive 390×844. Comprobar audio y zoom.
7. Mantener aparte otra terminal para los controles **del proyecto propio**:
   `run.py stop chat-messages`, `run.py start chat-messages`. No usar nombres de
   contenedores ajenos, prune, down -v ni eliminar volúmenes.

## Recorrido de grabación

| Tiempo | Pantalla y acción real | Qué decir | Resultado que debe verse |
|---|---|---|---|
| 0:00–0:25 | Repositorio público y diagrama de ENTREGA_FINAL | “React usa nuestro Gateway GraphQL. Este integra Chat, Threads, Integrales y Polls por REST.” | Componentes y comunicaciones, sin sugerir conexiones REST del navegador |
| 0:25–0:45 | Terminal: estado del Compose | “Los servicios y sus bases/brokers se ejecutan en un proyecto aislado; la red externa se llama microsvcs.” | Servicios saludables; migraciones completadas |
| 0:45–1:10 | Crear identidad A; copiar ID; cerrar y recuperar por ID | “Esta es identidad local, no autenticación con contraseña. El ID se valida contra Users y se conserva al recargar.” | Confirmación, nombre real, ID recuperado y recarga válida |
| 1:10–1:25 | Segundo perfil: crear identidad B | “Usaremos otra identidad para votar y comprobar restricciones.” | Segundo ID real, sin inyectarlo desde una base de datos |
| 1:25–1:50 | A: crear canal, buscarlo y seleccionarlo | “Los canales vienen del servicio; la búsqueda filtra esa lista. Crear y abrir actualiza la navegación.” | Canal real destacado, título/ruta correctos |
| 1:50–2:10 | Enviar mensaje y pulsar Actualizar mensajes | “La publicación se confirma por Gateway. Mostramos autor, fecha y contenido, sin duplicarlo al refrescar.” | Un mensaje, fecha/autor y editor limpio tras confirmación |
| 2:10–2:35 | Abrir Thread, responder, cerrar con Escape y volver a abrir | “La respuesta pertenece al mensaje raíz y usa Thread Service y su worker, no un mensaje normal ni un hilo anidado.” | Respuesta confirmada, panel cerrado/reabierto y mismo contenido |
| 2:35–3:00 | Integrales: calcular la definida entre 0 y 1 | “El servicio devuelve un resultado simbólico y, cuando corresponde, numérico.” | 1/3 y aproximadamente 0,333333; abrir detalle y recargar |
| 3:00–3:20 | Calcular indefinida con el ejemplo editable | “Las indefinidas conservan su constante. Esta interfaz presenta el LaTeX escapado del servicio.” | Resultado con + C; no atribuir composición tipográfica a esta versión |
| 3:20–3:45 | Calcular `x + 1`, filtrar Fallidas, usar Siguiente/Anterior y detalle | “Un cálculo fallido es un registro de dominio, no un falso éxito ni una caída de red. También persiste en el historial.” | `failed`/NOT_AN_INTEGRAL, filtro y segunda página reales |
| 3:45–4:15 | A: crear encuesta con el ID del canal; volver al chat | “La creación envía una clave de idempotencia. Polls publica el anuncio usando el mismo Messages que el Gateway.” | ID de encuesta y un anuncio en el canal; copiar enlace |
| 4:15–4:45 | B: abrir enlace, elegir opción, votar, actualizar resultados | “El voto usa el ID de opción. Los resultados se consultan nuevamente en el servicio.” | Voto registrado, total y barras correctas |
| 4:45–5:00 | B: recargar la encuesta abierta y volver a intentar el mismo voto | “El servidor también rechaza duplicados aunque se recargue la página.” | Error de conflicto y total sin aumentar |
| 5:00–5:20 | Mostrar ausencia del cierre en B; A cierra; B recarga | “La interfaz ofrece cierre al autor. El Gateway y servicio rechazan cierre ajeno y votos posteriores.” | Cerrada, Votar deshabilitado; evidencia de FORBIDDEN/CONFLICT en reporte si se explica el rechazo por API |
| 5:20–5:55 | Detener SOLO Messages propio; crear otra encuesta; arrancarlo | “Durante una caída, la encuesta queda pendiente y no admite votos. Al recuperar Messages se publica y pasa a abierta.” | pending_announcement → abierta; anuncio real. Cerrar esta encuesta al terminar |
| 5:55–6:20 | Mostrar modo oscuro, navegar a Integrales/Chat, recargar | “El layout y tema se conservan. La preferencia del sistema se usa hasta seleccionar un tema explícito.” | Sin layout duplicado ni pérdida de identidad/tema |
| 6:20–6:40 | Responsive móvil: menú, Chat y Thread; Escape/teclado y copiar | “La misma aplicación funciona en móvil; los controles también son utilizables con teclado.” | Sin overflow, panel móvil y retorno de foco |
| 6:40–7:15 | Mostrar prueba de reinicio o ejecutarla; volver al canal, integral y encuesta | “Reiniciamos las aplicaciones y las seis bases conservando volúmenes. Los mismos IDs se recuperan por GraphQL.” | Reporte before/after con StartedAt distintos; recarga real con datos persistidos |
| 7:15–7:40 | Network `/graphql`, resultados de tests y enlaces públicos | “La web solo consume GraphQL. Las fuentes docentes requieren tres copias corregidas localmente; sus repositorios originales no fueron alterados.” | Solo /graphql para datos; 550 tests aprobados, repos públicos y limitación externa visible |

Si ejecutar el reinicio durante la grabación demora más, conservar esa espera o
recortarla claramente; **no sustituir el resultado por respuestas simuladas**.
Para el paso de reinicio se usa el script existente, que actúa solo en el proyecto
ligado a `FINAL_STACK_DIR`:

```sh
node integration/overrides/persistence-e2e.cjs "$TAREA6_EVIDENCE/browser-report.json" "$TAREA6_EVIDENCE"
```

El reporte contiene los IDs del E2E previo. Si se quiere demostrar exactamente
los registros creados en cámara, repetir el mismo recorrido automatizado grabado
o preparar el reporte con los IDs devueltos por las APIs de esa demostración,
sin leer bases administrativamente. No afirmar que el reporte de otro recorrido
contiene los datos recién creados manualmente.

## Verificaciones y narración de fallos

- UI impide cierre ajeno y voto cerrado; los rechazos del servidor se verificaron
  además con GraphQL real. No inventar botones que no existen para esos casos.
- No reenviar mensajes/respuestas ante timeout. Mostrar borrador y resultado
  incierto, actualizar antes de repetir manualmente. El reporte de recuperación
  acredita un solo POST y la respuesta persistida tras reanudar Threads.
- El bot opcional, WebSockets, contraseñas, edición y Kubernetes no se presentan
  como funcionalidades implementadas de esta entrega.
- La integral fallida es esperada; un 500 de los servicios docentes originales
  **no** se describe como éxito. Explicar el parche local `insert_one(...copy())`.

## Grabación disponible y cierre de entrega

Se conservan dos videos **reales de los contextos Chromium** del E2E completo en
`/tmp/t6-final-20261109/videos/`. Sus nombres, hashes, duración y decodificación
sin errores están en
[evidencia_integracion_final/video-validation.json](evidencia_integracion_final/video-validation.json).
Son tomas automáticas breves, sin audio ni presentación de arquitectura; sirven
como evidencia complementaria, **no se afirma que ya exista un video docente
publicado**. No son una secuencia de capturas convertida en video.

No se subieron videos al repositorio ni a un servicio externo. Antes de entregar:

- [ ] Grabar la narración/presentación con este guion y comprobar reproducción.
- [ ] Mostrar todas las funcionalidades, no solo pantallas estáticas.
- [ ] Revisar que no aparezcan secretos ni datos ajenos.
- [ ] Publicar el video por el medio de entrega autorizado y agregar su enlace.
- [ ] Verificar que el profesor pueda abrir tanto el video como los repositorios.

**Enlace público del video: pendiente de adjuntar por el equipo.**
