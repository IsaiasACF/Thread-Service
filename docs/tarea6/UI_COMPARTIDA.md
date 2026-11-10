# Interfaz compartida y temas

La web utiliza una estructura persistente para identidad, chat, respuestas, integrales y encuestas. La barra lateral conserva canales, búsqueda y navegación; la cabecera mantiene el selector de tema en la misma posición. Cambiar de sección no desmonta esa estructura ni descarta un borrador de creación de canal.

## Dirección visual

Se aplicó la skill `frontend-design` con una dirección Swiss: Helvetica/Arial, superficies blancas o neutras, líneas finas, alineación izquierda y azul `#002FA7` como acento. La navegación utiliza un bloque azul, iconos SVG compartidos y estados activos por contraste. El modo oscuro adapta superficies y contraste conservando la distribución. No se añadieron cifras de ejemplo ni indicadores ficticios a la interfaz.

Los textos promocionales, símbolos Unicode usados como iconos y la cabecera alternativa de herramientas se sustituyeron por navegación común, títulos directos y un conjunto SVG local. El editor de integrales y su historial comparten una zona de trabajo con dos columnas en escritorio y una en móvil.

## Interacciones

- Buscar canales filtra los nombres ya obtenidos del servicio; no crea un buscador REST ni modifica los contratos.
- Los ejemplos de integrales rellenan y enfocan un editor editable. El cálculo solo se ejecuta al pulsar Calcular integral.
- Los botones de copia utilizan el portapapeles del navegador. Solo muestran confirmación si la escritura termina correctamente; ante un rechazo indican que debe seleccionarse el texto.
- Las opciones de encuesta responden a selección y foco. Los porcentajes y barras se calculan con los votos devueltos por Polls.
- El tema sigue inicialmente la preferencia del sistema y guarda la selección explícita en `thread.theme.v1`. Se conserva tras navegar y recargar.
- Las transiciones y el indicador animado de carga respetan `prefers-reduced-motion`.

La identidad local sigue sin ser autenticación. Se conservan el endpoint `/graphql`, las operaciones y las rutas acordadas. La lógica de servicios externos no cambia.

## Verificación

Se comprobaron 63 pruebas React y el build TypeScript/Vite. Se añadieron pruebas de persistencia de la estructura, tema, búsqueda, ejemplos y portapapeles. La regresión también comprueba que una creación tardía de canal no redirige si ya se cambió de sección.

La revisión de Chromium contra el entorno Docker real produjo 12 capturas de escritorio y móvil, en claro y oscuro. Verifica las dimensiones comunes de la estructura, ausencia de desbordamiento horizontal, tema persistente, preferencia del sistema, menú móvil, búsqueda, portapapeles y movimiento reducido. El reporte y las capturas están en [evidencia_ui_interactiva](evidencia_ui_interactiva).

También se repitió el recorrido funcional completo con servicios reales: identidad, canal, mensaje, respuesta, integrales exitosa/fallida, historial/detalle, encuesta con dos identidades, voto, resultados y cierre. Se registraron 67 solicitudes de datos exclusivamente a `/graphql`. Los rechazos de voto duplicado, cierre ajeno y voto tras cierre se mantuvieron. Evidencia en [functional/browser-report.json](evidencia_ui_interactiva/functional/browser-report.json).

La web local queda actualizada en http://localhost:5173. Esta etapa no incluye merge ni despliegue Kubernetes. Para integrar el PR, revisar con A los cambios de estructura, estilos y componentes compartidos, además de los módulos de B.
