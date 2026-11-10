# Integrales y Polls — Integrante B

Esta guía describe los módulos de B en la rama `feature/tarea6-polls-integrals`, creada desde `origin/main` en `117c432`. Usa el contrato compartido en `docs/tarea6/CONTRATO_COMPARTIDO.md`. Conserva el esquema GraphQL y las APIs externas. El alcance final incluye cambios de interfaz compartida solicitados por el usuario: estructura persistente, estilos, componentes y temas; se detallan en [UI_COMPARTIDA.md](UI_COMPARTIDA.md). La lógica REST de Chat/Threads permanece sin cambios.

## Funciones implementadas

- Gateway: cálculo, historial y detalle de integrales; creación, consulta, voto y cierre de encuestas. Los clientes validan entradas y respuestas, convierten campos a camelCase en los resolvers y usan el transporte/error común.
- Integrales: formulario LaTeX de hasta 1000 caracteres, resultado calculado o fallido, constante `+ C`, valor numérico, historial paginado, filtros y detalle compartible. El texto se representa escapado por React, sin inyectar HTML; esta versión muestra código LaTeX, todavía sin composición tipográfica de fórmulas.
- Polls: abrir por ID, formulario de creación con canal explícito, enlace al resultado, voto por `optionId`, resultados, cierre del autor y estados pendiente/abierto/cerrado/fallido. Las encuestas abiertas o pendientes se consultan cada 5 segundos sin refresco de fondo.
- Se reutilizan la identidad y el cliente GraphQL de A. El enlace compartido puede consultarse sin identidad; las escrituras requieren una identidad validada. La entrada del canal en el formulario es por ID. El rediseño compartido conserva los recorridos de Chat/Threads y añade búsqueda de canales.
- Todas las peticiones de la web usan `/graphql`; las mutaciones tienen `retry:false`. Un fallo de cálculo conserva el texto. La creación de encuesta reutiliza la clave de idempotencia para el mismo cuerpo mientras el formulario permanece montado; cambiar el cuerpo genera otra clave. No se promete persistencia de esa clave tras recargar la página.

El timeout de cálculo es 30 segundos, independiente del timeout HTTP compartido. Es un límite operativo inicial que debe medirse contra el servicio real. Los HTTP 201 con integral fallida y 202 con encuesta pendiente se devuelven como datos de dominio, sin simular éxito de cálculo/publicación.

## Integración local

El override `integration/overrides/polls-integrals.yaml` se combina con `integration/compose.yaml`. Lee fuentes externas desde rutas absolutas, sin copiarlas a este repositorio ni modificar sus APIs. Las revisiones utilizadas se registran en `polls-integrals.sources.json`; comprobar que los checkouts correspondan a esos commits antes del build. El archivo de versiones es un registro, no fuerza automáticamente el checkout.

Requisitos: Docker Engine funcionando, chat base y Threads accesibles en la red exacta `microsvcs`, fuentes externas disponibles en los commits registrados. Polls debe usar el mismo Messages que usa el Gateway. No usar estos overrides para desplegar copias de equipos ajenos en Kubernetes.

En PowerShell, establecer las rutas de los checkouts y validar la composición:

```powershell
$env:INTEGRALS_SOURCE_DIR = 'C:/ruta/modulo-integrales/integrals'
$env:POLLS_SOURCE_DIR = 'C:/ruta/INF326-Microservicio-Polls'
docker compose -f integration/compose.yaml -f integration/overrides/polls-integrals.yaml config --quiet
docker compose -f integration/compose.yaml -f integration/overrides/polls-integrals.yaml up --build -d
```

El override configura `POLLS_BASE_URL=http://polls-api:8004`, corrigiendo la URL predeterminada del scaffold. Integra migraciones de PostgreSQL antes de Polls, sin publicar los puertos de bases, brokers ni APIs externas. Solo las APIs usan `microsvcs`; bases/brokers usan redes privadas con nombres independientes. Las contraseñas incluidas son exclusivamente de desarrollo local, no las credenciales aportadas por el usuario.

El servicio Integrales inicia su consumidor según su implementación existente y puede registrar la identidad del bot. Su broker privado no recibe eventos de Messages: el bot no está integrado ni se considera una función entregada. La integración REST no depende de esos eventos.

Verificar en la web: calcular una integral, consultar detalle/historial; crear encuesta con un canal/autor válidos, abrir su enlace desde otra identidad, votar y cerrar como autor. Un estado pendiente debe actualizarse hasta la publicación o fallo. Reiniciar servicios y comprobar que sus datos permanecen antes de afirmar persistencia real.

## Pruebas y límites de validación

Las pruebas Gateway usan `httpx.MockTransport` para comprobar las siete operaciones, rutas y cuerpos REST, conversiones camelCase, validación, errores, ausencia de reintentos e idempotencia. Las pruebas React validan documentos GraphQL contra el snapshot compartido e interceptan exclusivamente `/graphql`. Incluyen resultados/fallos, preservación del texto, filtro/detalle, voto por ID, cierre, estado pendiente y reutilización de clave tras error.

Se actualizaron dos pruebas de compatibilidad previas que exigían placeholders o errores `NOT_IMPLEMENTED`: `frontend/src/app/App.test.tsx` y el caso de aislamiento en `gateway/tests/test_chat_graphql.py`. No cambian el contrato ni el comportamiento de Chat/Threads.

Validación final: 323 pruebas Gateway aprobadas, 63 pruebas React aprobadas, build TypeScript/Vite aprobado y composición Docker válida. Se conserva el snapshot GraphQL v1 sin modificaciones. Las pruebas incluyen la regresión de Chat/Threads, los temas y las interacciones compartidas.

Se inició Docker Desktop y se ejecutó la integración completa con contenedores reales. Chromium completó los recorridos de Chat/Threads, Integrales y Polls sin mocks ni interceptores; se verificaron además recuperación de Messages, idempotencia, aislamiento ante caída de Polls y persistencia tras reiniciar MongoDB/PostgreSQL de B. Resultados y reproducción en [VALIDACION_INTEGRALES_POLLS_B.md](VALIDACION_INTEGRALES_POLLS_B.md). No se inspeccionó ni modificó Kubernetes.

## Pendientes para integrar y entregar

1. Aprobar la revisión del módulo Gateway de B y sus pruebas; mantener el esquema compartido intacto.
2. Revisar con A los cambios de estructura, estilos, componentes y pruebas compartidas; el acceso al formulario de encuestas desde el canal seleccionado sigue siendo una mejora opcional para evitar ingresar el ID manualmente.
3. Revisar la evidencia del stack local real ya ejecutado: voto duplicado, cierre ajeno, recuperación de Messages y persistencia comprobados. Se conserva la evidencia previa de Chat de A.
4. Verificar endpoints reales de Integrales y Polls para Kubernetes con A; no redesplegar servicios ajenos. Configuración principal, CI e integración final siguen bajo responsabilidad de A.
5. Preparar participación de B en el video usando la evidencia real registrada. La validación local no sustituye las pruebas futuras de Kubernetes.
