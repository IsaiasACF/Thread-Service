# Validación real de Integrales y Polls — B

El 9 de noviembre de 2026 se inició Docker Desktop y se levantaron los servicios locales para completar los recorridos de B. La web quedó accesible en **http://localhost:5173**, con Gateway en **http://localhost:5000/health**. La ejecución no implicó merge ni cambios en Kubernetes.

## Resultado comprobado

| Recorrido | Evidencia / resultado |
|---|---|
| Identidad, canal, mensaje y respuesta | Creados desde React y confirmados por Gateway y servicios reales |
| Integral resoluble | Integral definida de x² entre 0 y 1: resultado simbólico 1/3 y numérico equivalente |
| Integral fallida | `x + 1` produce `failed` con `NOT_AN_INTEGRAL`, presentado como dato de dominio |
| Historial y detalle | Filtro por fallidas, enlace de detalle y recarga desde URL directa |
| Encuesta con dos identidades | Creación, acceso por enlace, voto por ID de alternativa y resultados actualizados |
| Rechazos | Voto duplicado: `CONFLICT`; cierre ajeno: `FORBIDDEN`; voto nuevo tras cierre: `CONFLICT` |
| Cierre | Autor cierra; otra sesión recarga y muestra encuesta cerrada y voto deshabilitado |
| Navegador | 55 solicitudes de datos, todas al mismo origen y ruta `/graphql`; cero errores de ejecución de página |
| Disposición móvil | Captura a 390 px y comprobación de ausencia de desbordamiento horizontal |
| Messages no disponible | La creación queda pendiente, no permite votar y luego se activa automáticamente al recuperar Messages |
| Idempotencia real | Mismo cuerpo y clave conservan el ID; cuerpo distinto con la misma clave produce `CONFLICT` |
| Anuncio | La encuesta recuperada aparece en el mismo Messages utilizado por el Gateway |
| Polls no disponible | Chat, respuestas e integrales siguen respondiendo; consultar Polls produce `UPSTREAM_UNAVAILABLE` |
| Persistencia | Reinicio real de MongoDB de Integrales y PostgreSQL de Polls: mismos IDs, cálculo/fallo y encuesta cerrada con un voto |

Los resultados de consultas anteriores y posteriores al reinicio son idénticos en los campos comprobados. Se registran tiempos `StartedAt` distintos de ambos contenedores de bases para demostrar el reinicio. Esto verifica persistencia en los volúmenes locales utilizados; no prueba backups ni recuperación de un disco perdido.

## Entorno y límites

Se crearon tres proyectos Compose aislados: `thread-b-base`, `thread-b-threads` y `thread-b-app`. Comparten la red existente `microsvcs`; no se borró ni se cambió la propiedad de esa red. Los volúmenes pertenecen a esos proyectos. No se accedió a bases ni servicios compartidos del clúster.

La base de chat utilizada es la que el usuario agregó localmente en `users/`, `channels/`, `messages/` y `docker-compose.demo.yaml`. Ya contenía `insert_one(...copy())`: no es una afirmación de que la versión docente original esté corregida. Sus hashes están en `versions.json`. No se modificaron esas fuentes durante esta validación.

Integrales y Polls se descargaron en una carpeta temporal fuera del repositorio y se fijaron a las revisiones de [polls-integrals.sources.json](../../integration/overrides/polls-integrals.sources.json). No se modificaron sus repositorios. Los IDs de las pruebas se obtuvieron de respuestas públicas de las APIs; no se recuperaron desde bases ni se fabricaron fixtures para simular éxitos.

La representación de fórmulas sigue siendo LaTeX escapado y valor numérico, sin composición tipográfica matemática. El bot de Integrales continúa fuera del alcance validado. El servicio externo puede crear su identidad de bot durante su arranque, pero su broker privado no recibe eventos de Messages.

El primer intento del navegador se detuvo por un selector demasiado estricto del filtro Estado. Se corrigió el selector del script para usar el rol `combobox`; no se alteró la respuesta de ningún servicio ni la expectativa funcional. El reporte y la captura de ese intento se conservan en `attempt-01/`. El segundo intento pasó completo. No se detectaron fallos funcionales que exigieran cambiar el Gateway o las pantallas durante esta etapa.

## Evidencias

Los archivos están en [evidencia_integrales_polls](evidencia_integrales_polls):

- [Reporte Chromium](evidencia_integrales_polls/browser-report.json): pasos, IDs reales, solicitudes observadas y estado final aprobado.
- [Recuperación e idempotencia](evidencia_integrales_polls/recovery-report.json): caída de Messages, activación posterior y aislamiento de Polls.
- [Persistencia](evidencia_integrales_polls/persistence-report.json): consultas antes/después y reinicios de bases.
- [Versiones y fuentes](evidencia_integrales_polls/versions.json), [contenedores](evidencia_integrales_polls/containers.json) e [imágenes](evidencia_integrales_polls/images.json).
- Capturas `01`–`09`: chat, cálculo, fallo/historial, encuesta abierta, voto/resultados, cierre, móvil, pendiente y recuperación.
- `checksums.sha256`: hashes de los archivos de evidencia, sin incluir el propio manifiesto.

Los reportes no contienen contraseñas, kubeconfig, variables de entorno de contenedores ni logs de infraestructura. Los datos mostrados son identidades y contenido creados para estas pruebas locales.

## Reproducir el arranque

Requisitos: Docker Desktop funcionando, la base local provista y los checkouts externos en las revisiones registradas. La base local (`users/`, `channels/`, `messages/`, `docker-compose.demo.yaml`) ya estaba en el equipo y queda fuera del PR de B: estos comandos requieren disponer de ella y contrastar sus hashes con `versions.json`. Para preparar fuentes docentes verificadas y copias corregidas externas, A documenta su procedimiento en [CHAT_E2E_FINAL.md](CHAT_E2E_FINAL.md); no se debe asumir que un checkout docente original equivale a la base local utilizada aquí. Crear la red `microsvcs` solo si no existe; en esta ejecución ya existía. Los comandos se ejecutan desde la raíz del repositorio.

```powershell
docker compose -p thread-b-base -f docker-compose.demo.yaml -f integration/overrides/chat-base-local.yaml up --build -d
docker compose -p thread-b-threads -f docker-compose.yaml up --build -d
$env:INTEGRALS_SOURCE_DIR = Join-Path $env:TEMP 'thread-b-real-20261109/integrals-source/integrals'
$env:POLLS_SOURCE_DIR = Join-Path $env:TEMP 'thread-b-real-20261109/polls-source'
docker compose -p thread-b-app -f integration/compose.yaml -f integration/overrides/polls-integrals.yaml up --build -d
```

Las rutas temporales anteriores corresponden a esta ejecución. Si se usan otras carpetas, asignar sus rutas absolutas. No copiar fuentes ajenas a este repositorio ni cambiar el `MESSAGES_BASE_URL` a otro chat: los IDs deben referenciar el mismo entorno.

## Reproducir las pruebas

Se instaló Playwright en la carpeta temporal y se reutilizó Chromium ya instalado. El primer argumento de los scripts es la ruta absoluta al módulo `playwright`; el último es el ejecutable de Chromium. Se pueden reemplazar por rutas equivalentes.

```powershell
$browserModule = Join-Path $env:TEMP 'thread-b-real-20261109/browser/node_modules/playwright'
$chromium = Join-Path $env:LOCALAPPDATA 'ms-playwright/chromium-1223/chrome-win64/chrome.exe'
$evidence = 'docs/tarea6/evidencia_integrales_polls'
node integration/overrides/browser-e2e.cjs $browserModule $evidence $chromium
node integration/overrides/recovery-e2e.cjs $browserModule "$evidence/browser-report.json" $evidence $chromium
node integration/overrides/persistence-e2e.cjs "$evidence/browser-report.json" $evidence
```

Las pruebas crean datos nuevos. Los scripts de recuperación/persistencia detienen y restauran únicamente contenedores `thread-b-*` especificados en su código. No apuntarlos a infraestructura compartida ni cambiar esos nombres para intervenir servicios ajenos. El test principal solo lee y opera las APIs mediante la interfaz y `/graphql`; no intercepta respuestas.

La validación inicial utilizó 323 pruebas Gateway y 57 React aprobadas. Tras el rediseño compartido, la suite React aumentó a 63 aprobadas y el build TypeScript/Vite volvió a pasar. El recorrido funcional se repitió y sus resultados están en [UI_COMPARTIDA.md](UI_COMPARTIDA.md). La validación real complementa esas suites.

## Estado dejado para revisión

La aplicación y sus servicios de prueba quedan levantados, con Messages y Polls restaurados. Los datos y volúmenes se conservan. El siguiente paso es revisar los cambios de B y preparar el PR con A; el despliegue Kubernetes y el video siguen pendientes.
