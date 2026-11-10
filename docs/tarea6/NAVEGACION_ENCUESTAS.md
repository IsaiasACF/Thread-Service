# Buscar y crear encuestas desde la web

Esta guía describe los controles de encuestas para quienes usan y mantienen el frontend.

## Abrir y filtrar encuestas

1. Entra a un canal del chat y selecciona **Encuestas**. El canal queda preseleccionado para buscar y crear.
2. En **Filtrar encuestas por canal**, elige un canal por su nombre.
3. Opcionalmente, selecciona un estado en **Estado de las encuestas**.
4. Elige la pregunta en **Encuestas disponibles** para abrir sus alternativas, resultados y acciones.
5. Usa **Actualizar encuestas** para volver a consultar los anuncios y sus detalles.

También puedes abrir una encuesta con su enlace o con **ID de encuesta**.

## Crear una encuesta

Selecciona **Canal para la encuesta**, escribe la pregunta y sus alternativas, establece la duración y pulsa **Crear encuesta**. La encuesta aparece en el desplegable durante la sesión, incluso si su anuncio todavía está pendiente. Confirma el canal y el estado al abrirla.

## Alcance de la lista

Polls permite consultar por ID, pero no listar por canal. El frontend obtiene los mensajes del canal mediante GraphQL, extrae las referencias `Poll ID: UUID` y consulta cada encuesta mediante el Gateway. Comprueba que cada resultado pertenezca al canal elegido y utiliza la pregunta y el estado devueltos por Polls.

La búsqueda consulta hasta las 25 referencias distintas más recientes, con un máximo de tres consultas simultáneas. La interfaz avisa si alcanza ese límite o si algunas consultas fallan. No constituye un catálogo completo: una encuesta sin anuncio accesible puede abrirse por enlace o ID.

**Recientes de esta sesión** reúne hasta 100 encuestas creadas o abiertas en la memoria del navegador. Esta lista no se conserva al recargar la página. Las referencias del chat se vuelven a consultar al seleccionar un canal.

La implementación conserva las APIs externas y el contrato GraphQL. La red Docker sigue siendo `microsvcs`.

## Validación

- 68 pruebas de React aprobadas y compilación TypeScript/Vite correcta.
- Navegador con servicios locales reales: descubrimiento por canal, apertura sin escribir ID, filtros por estado y canal, creación mediante selector y actualización del desplegable.
- Vista móvil de 390 píxeles en modo oscuro sin desbordamiento horizontal.
- Todas las solicitudes de datos observadas pasan por `/graphql`; no se detectan errores de JavaScript.

La comprobación reproducible está en [poll-navigation-check.cjs](../../integration/overrides/poll-navigation-check.cjs). Recibe la ruta del módulo Playwright, el archivo de fixtures del entorno local, el directorio de salida y el ejecutable Chromium. Crea una encuesta de prueba y la cierra al terminar.

Consulta el [resultado de la ejecución](evidencia_navegacion_encuestas/report.json) y las capturas de [escritorio](evidencia_navegacion_encuestas/01-listado-y-detalle.png) y [móvil oscuro](evidencia_navegacion_encuestas/03-selectores-movil-oscuro.png).
