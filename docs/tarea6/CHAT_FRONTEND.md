# Tarea 6 — Interfaz React de Chat y Threads (A)

Rama: `feature/tarea6-chat-frontend`, desde main actualizado con el merge del
PR #5 (`4d7bb4d953b499c6456d2876043b8e3068efa435`). El repositorio estaba limpio.
Esta entrega utiliza el [contrato compartido v1](CONTRATO_COMPARTIDO.md) y las
[nueve operaciones del Gateway de A](CHAT_GATEWAY.md), sin modificarlos.

## Pantallas y navegación

- `/`: creación de identidad, selección por ID existente y resumen de identidad
  activa. Crear o seleccionar no implica autenticación con contraseña.
- `/channels`: vista inicial para elegir o crear un canal.
- `/channels/:channelId`: conversación, validada mediante `channel(id)` antes
  de consultar mensajes. Un canal inexistente no se presenta como chat vacío.
- Threads se abre desde un mensaje de la conversación, sin agregar rutas de
  dominio ni interpretar una respuesta como mensaje raíz.
- `/integrals`, `/integrals/:id` y `/polls/:pollId` conservan componentes y rutas
  de Andrés. Sus funcionalidades pendientes no se consultan desde Chat.

En escritorio, el espacio de trabajo ocupa tres áreas: canales e identidad a
la izquierda, conversación en el centro y Threads a la derecha cuando está
abierto. Los mensajes propios tienen fondo azul claro y se alinean a la derecha.
En móvil, los canales se abren desde un botón accesible, el chat ocupa la
pantalla y Threads se presenta como un panel superpuesto con fondo atenuado.

El panel tiene nombre accesible, cierre con botón o Escape, foco inicial,
retorno al mensaje que lo abrió y contención del foco de teclado en móvil.
Las fechas se presentan en español y en la zona horaria del navegador; se
conserva el timestamp ISO original en `<time datetime>`. El texto se renderiza
como texto React, con saltos de línea y ajuste de palabras largas, sin HTML.

## Archivos, componentes y hooks

| Archivo / carpeta | Responsabilidad |
|---|---|
| `features/identity/api.ts` | User, getUser/createUser y claves de caché de usuarios |
| `features/identity/IdentityProvider.tsx` | Identidad compartida, restauración y validación |
| `features/identity/IdentityPage.tsx` | Formularios de nombre e ID |
| `features/chat/api.ts` | Operaciones de canales, mensajes y respuestas; DTOs GraphQL |
| `features/chat/Workspace.tsx` | Sidebar, canales, creación y navegación a herramientas |
| `features/chat/ChatPage.tsx` | Validación del canal, conversación y selección de hilo |
| `features/chat/MessageCard.tsx`, `Author.tsx` | Mensaje, autor, fecha y acción de hilo |
| `features/chat/Composer.tsx` | Editor compartido de mensajes y respuestas |
| `features/chat/errors.ts` | Códigos públicos, errores de lectura/escritura, orden y límites |
| `features/chat/useTimelineScroll.ts` | Seguir actividad al final sin interrumpir lectura anterior |
| `features/chat/Chat.module.css` | Diseño de A, sin cambios de estilos internos de B |
| `features/threads/ThreadsPanel.tsx` | Mensaje original, respuestas y accesibilidad del panel |

Los hooks de TanStack Query se usan en cada componente para que su ciclo de
vida coincida con la vista activa. El código de A reutiliza Button, EmptyState,
ErrorMessage y LoadingIndicator, el QueryClientProvider y el cliente GraphQL
existentes. No incorpora bibliotecas visuales ni dependencias nuevas.

### Operaciones utilizadas

| Operación GraphQL | Uso |
|---|---|
| `GetUser` → `user(id)` | Verificar identidad y resolver nombres de autores |
| `CreateUser` → `createUser(displayName)` | Crear identidad y guardar su ID confirmado |
| `GetChannels` → `channels` | Listar canales |
| `GetChannel` → `channel(id)` | Verificar canal antes de mostrar conversación |
| `CreateChannel` → `createChannel(name)` | Crear canal, actualizar listado y navegar |
| `GetMessages` → `messages(channelId)` | Leer y actualizar conversación |
| `SendMessage` → `sendMessage(...)` | Publicar mensaje con autor verificado |
| `GetReplies` → `replies(channelId, messageId)` | Leer solo el hilo abierto |
| `CreateReply` → `createReply(...)` | Responder al mensaje raíz seleccionado |

Todas las funciones usan exclusivamente `frontend/src/lib/graphql.ts`, con
`/graphql` del mismo origen. Las consultas transmiten AbortSignal. No hay fetch
REST, URLs de microservicios, clientes GraphQL adicionales ni WebSockets en React.

## Identidad local

La clave `thread.identity.v1` de localStorage guarda únicamente `{ "id": "..." }`.
Al recuperar una identidad se consulta `user(id)`; un ID almacenado o un nombre
en el storage no autorizan escrituras por sí mismos. El nombre visible procede
de la respuesta GraphQL, nunca de un dato almacenado sin verificar.

- Si el usuario existe, se habilitan los formularios de mensajes y respuestas.
- Durante validación o indisponibilidad, se permite lectura pero se bloquean
  escrituras hasta contar con identidad válida.
- Un error temporal conserva el ID y permite revalidar sin borrarlo.
- Si el recurso devuelve null o NOT_FOUND, se elimina el ID persistido y se
  permite seleccionar otra identidad.
- Cambiar identidad vuelve a verificar el nuevo ID; cerrar identidad elimina
  el ID local y deshabilita escritura, sin pretender cerrar una sesión de servidor.
- Una confirmación tardía no reactiva una identidad que el usuario ya cerró ni
  selecciona una identidad desde una pantalla abandonada.
- Si localStorage está restringido por el navegador, la identidad funciona en
  memoria y se muestra que no podrá conservarse después de recargar.

No hay contraseñas, tokens, roles, membresías ni garantías de autenticación.
Los nombres se validan entre 1 y 80 caracteres. Los límites de nombres y contenido
cuentan puntos de código Unicode, como Pydantic; no aplican un límite UTF-16
más estricto a texto con emoji. La creación recorta espacios exteriores del nombre.

## Caché, refresco y cancelación

| Recurso | Clave TanStack Query | Política |
|---|---|---|
| Usuario | `['users', id]` | Consulta compartida por autores e identidad |
| Canales | `['channels']` | Consulta al abrir sidebar e invalidación al crear |
| Canal | `['channel', id]` | Validar al abrir; revalidar cada 30 s |
| Mensajes | `['messages', channelId]` | Consulta al abrir y polling cada 5 s |
| Respuestas | `['replies', channelId, messageId]` | Consulta/polling cada 5 s solo con panel abierto |

TanStack Query evita solapar solicitudes pendientes del mismo recurso. No se
mantienen datos de otro canal como placeholder al cambiar de ruta. Consumir
AbortSignal permite cancelar lecturas al cambiar de canal, cambiar de mensaje,
cerrar Threads o abandonar la vista. El polling no continúa en segundo plano
con la pestaña oculta y se detiene al desmontar la conversación o el panel.

Los autores comparten caché por ID, con cinco minutos de frescura, sin retry ni
refetch al montar de nuevo tras error. Los mensajes de un mismo autor no generan
una consulta por fila en cada refresco. Si no puede resolverse el nombre, aparece
el ID y la conversación sigue operativa. El autor activo usa la identidad validada.

Después de una escritura **confirmada** se cancela la lectura concurrente de su
lista, se incorpora la respuesta real por ID sin duplicados y se invalida esa
clave para recuperar el listado. No hay escrituras optimistas ni IDs inventados.
Las listas se ordenan por fecha y luego ID. La creación de canal actualiza la
lista y abre su ruta; una respuesta tardía no redirige si ya se abandonó la pantalla.

El scroll sigue las novedades si el lector estaba al final, y revela su propia
publicación confirmada. Al leer mensajes anteriores, el polling no fuerza el
retorno al final. Los borradores pertenecen a la conversación o hilo abierto;
no se prometen persistidos entre cambios de canal o recargas.

## Formularios y errores

El editor admite saltos de línea, cuenta caracteres y valida entre 1 y 4000.
Threads rechaza respuestas de solo espacios, conforme al recorte del servicio.
Mientras un POST está pendiente se deshabilitan el editor y el botón de envío.
El borrador solo se vacía después de la confirmación del Gateway.

El cliente graphql-request procesa errores GraphQL incluso en HTTP 200. La UI
usa códigos del contrato y mensajes propios; nunca muestra cuerpos externos,
trazas ni el mensaje privado de una excepción. Lecturas contemplan carga,
error, reintento, vacío, datos y recursos inexistentes.

- VALIDATION_ERROR pide revisar datos; NOT_FOUND/GONE informa recurso ausente.
- FORBIDDEN/CONFLICT indican rechazo o conflicto.
- Timeouts, desconexión, error interno o respuesta externa incompatible durante
  una creación se consideran resultado incierto: pueden haber persistido.
- Los retries de TanStack Query están deshabilitados. Las consultas activas
  pueden consultar otra vez en su siguiente intervalo o al actualizar manualmente;
  las mutaciones nunca se repiten automáticamente.
- Mensajes y respuestas conservan el borrador ante fallas y ofrecen actualizar
  la lista antes de repetir manualmente. El polling puede mostrar posteriormente
  una escritura aplicada aunque su confirmación se haya perdido.
- Un error de lectura de autores no bloquea el chat. Un mensaje raíz ausente
  bloquea el formulario del hilo y muestra un error específico.

No se ofrecen edición, eliminación, respuestas anidadas ni recuentos de todos
los hilos mediante consultas individuales.

## Cambios compartidos y compatibilidad con B

Solo se ajustaron estos archivos compartidos de implementación/pruebas:

- `src/app/App.tsx`: incorpora IdentityProvider y usa Workspace únicamente para
  `/` y `/channels...`. Las otras rutas conservan el layout anterior. El enlace
  Chat pasa de un ID ficticio a `/channels`, vista válida de selección.
- `src/app/App.test.tsx`: reemplaza los casos placeholder de A por navegación
  funcional y conserva regresiones de las tres rutas de B y la ruta desconocida.
- `vitest.config.ts`: el runner Node lee el snapshot GraphQL inalterado y lo
  inyecta solo a los tests para validar cada documento contra el schema. No se
  amplía el acceso de archivos de Vite ni se incluyen APIs Node en el bundle.

No se modifican APIs de componentes compartidos, tokens globales, Providers,
cliente GraphQL, dependencias/lockfile, contratos, Gateway ni módulos de B.
El registro automático de `features/*/routes.tsx` permanece vigente: Andrés
puede implementar sus páginas y rutas sin editar los módulos de Chat/Threads.
Su layout continúa funcionando y un error de identidad no impide renderizarlo.
Si existe un ID guardado, el proveedor puede revalidarlo en cualquier ruta;
esta validación nunca bloquea las páginas de B.

## Arranque

Node 22.12 o superior (el archivo `.nvmrc` selecciona 22). Desde raíz:

```sh
python3.12 -m venv /tmp/thread-gateway-venv
/tmp/thread-gateway-venv/bin/pip install -r gateway/requirements-dev.txt
cp gateway/.env.example gateway/.env
# Configurar URLs de un stack LOCAL de prueba.
cd gateway
/tmp/thread-gateway-venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 5000 --reload
```

En otra terminal, desde raíz:

```sh
cd frontend
npm ci
# Opcional: cp .env.example .env
npm run dev
```

Abrir http://localhost:5173. Vite reenvía `/graphql` al Gateway de localhost:5000;
`GATEWAY_PROXY_TARGET` cambia ese destino para un entorno local diferente.
No se agregan variables VITE_* ni direcciones de microservicios al navegador.
El Compose existente usa puertos 5000/5173 y red externa `microsvcs`; consultar
el contrato compartido para iniciarlo cuando exista Docker disponible.

## Pruebas y resultados

Desde frontend/, con Node 22:

```sh
npm ci
npm test
npm run build
```

Desde raíz, con entornos Python separados:

```sh
/tmp/thread-gateway-venv/bin/python -m pytest -c gateway/pytest.ini gateway/tests -q -W error
/tmp/thread-original-venv/bin/python -m pytest -q -W error
/tmp/thread-original-venv/bin/python -m pytest scripts/test_k8s_rendering.py -q -W error
docker compose -f integration/compose.yaml config --quiet
git diff --check
```

Resultados locales del 2026-11-08:

| Comprobación | Aprobadas | Fallidas | Omitidas |
|---|---:|---:|---:|
| Frontend Vitest / Testing Library | 48 | 0 | 0 |
| Gateway completo | 263 | 0 | 0 |
| Thread Service original | 101 | 0 | 6 |
| Kubernetes offline | 20 | 0 | 0 |
| **Total** | **432** | **0** | **6** |

Instalación `npm ci`, TypeScript, build de Vite y validación Compose correctos.
Las seis omisiones originales requieren MongoDB/RabbitMQ de prueba; nunca se
apuntaron a datos del clúster para completar la regresión.

Las pruebas automatizadas usan fetch controlado **a través del cliente GraphQL
real compartido**. Cada documento se valida contra el snapshot v1 original.
Cubren identidad/recarga/cambio/cierre/indisponibilidad, canales, orden, autores,
publicación, borradores ante errores HTTP 200, límites Unicode, no duplicación,
POST pendiente, cancelación, solicitudes sin solapamiento, polling activo y
cierre de hilos, errores de raíz y compatibilidad con rutas de B.
Los nueve documentos GraphQL se ejecutan también en el recorrido de navegador.

## Capturas y recorrido de navegador

Capturas del frontend real servido por Vite, con **datos ficticios y GraphQL
interceptado**, en Chromium mediante Playwright. No contienen datos del curso:

| Captura | Pantalla |
|---|---|
| [01 — Identidad](evidencia_frontend/01-identidad.png) | Crear, seleccionar y consultar identidad local |
| [02 — Chat y Threads en escritorio](evidencia_frontend/02-chat-threads-escritorio.png) | Tres paneles, mensajes propios y respuesta |
| [03 — Threads en móvil](evidencia_frontend/03-thread-movil.png) | Panel superpuesto y formulario |
| [04 — Chat en móvil](evidencia_frontend/04-chat-movil.png) | Conversación principal y navegación plegable |

El recorrido de navegador comprobó crear identidad y canal, publicar y leer
mensaje, abrir hilo, publicar y volver a consultar respuesta, recargar y recuperar
identidad verificada y registros simulados, navegar a Integrales y ausencia de
errores de página. Se revisaron anchos 320, 390, 768, 1024 y 1440 sin desplazamiento
horizontal; capturas en 1440×1000 y 390×844. Playwright/Chromium se instalaron en
`/tmp` como herramientas de QA, sin agregarlos a dependencias del proyecto.

## Integración real y límites

**No se logró un recorrido contra microservicios reales en este PR.** Se intentó
comprobar Docker y el daemon no está disponible. No se utilizó Kubernetes como
sustituto ni se hicieron escrituras, modificaciones o despliegues en el clúster.

La comprobación de recarga en navegador prueba la persistencia local del ID y
el consumo de respuestas GraphQL simuladas. El backend de esa prueba conserva
los registros solo en memoria del fixture: **no demuestra persistencia real de
MongoDB, publicación de eventos ni integración real Gateway→microservicios**.
La suite de Gateway también utiliza sus transportes de prueba deterministas.

Queda pendiente repetir el mismo recorrido en un stack local aislado con los
servicios reales y verificar serialización y persistencia. Se mantienen los
límites documentados en CHAT_GATEWAY.md, incluida la semántica de Messages al
listar un canal inexistente; la UI consulta `channel(id)` antes de abrirlo.
Esta entrega no incluye autenticación segura, despliegue, integración de Polls/
Integrales, video final ni cambios de servicios externos.
