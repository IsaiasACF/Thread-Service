# Guion de video: QA de Thread Service — Tarea 7

## Alcance y estado

Presentadores: **Isaías (integrante A)** y **Andrés (integrante B)**.

Formato: demostración de pantalla **sin narración**, con títulos breves y pausas para leer los comandos y resultados. Duración orientativa: **5–7 minutos**, según la construcción y el arranque de Docker. Se pueden recortar esperas, identificando el corte.

Este guion cubre la Tarea 7: pruebas de servicio, aislamiento, contratos e integración de Threads con Users, Channels y Messages. Se prepara a partir de [la planificación](planificacion.md). El alcance confirmado corresponde únicamente a la Tarea 7.

**Estado al redactar:** en este checkout existe la planificación; todavía no están los archivos `tests/test_qa_service.py`, `tests/test_qa_contract.py` ni `integration/qa/`. Los comandos nuevos son los previstos por el plan. Antes de grabar, sustituirlos por los comandos realmente implementados y verificar sus resultados. El guion no acredita que la tarea ya esté terminada.

## Preparación fuera de cámara

1. Integrar los PR de Isaías y Andrés y registrar el SHA sobre el que se graba. Revisar la matriz de endpoints, las instrucciones y los reportes de esa revisión.
2. Instalar las dependencias y preparar las fuentes verificadas fuera del repositorio. Registrar revisión del proveedor, hashes y modo original/corregido si aplica el parche conocido de serialización.
3. Preparar un proyecto Compose exclusivo de QA. No usar datos ni contenedores de Tarea 6, servicios del clúster o bases ajenas.
4. Abrir el editor con los tests relevantes y una terminal legible. Ocultar tokens, archivos de entorno, historial de comandos sensibles y datos personales.
5. Reservar otra terminal para el runner de integración. Mantener visible únicamente el estado de los servicios y salidas sanitizadas; no mostrar un `docker inspect` completo ni archivos privados.
6. Preparar títulos de sección y ajustar zoom. Al escribir campos de demostración, usar escritura progresiva y nombres naturales: Andrés, Isaías y Grupo de estudio.
7. Ejecutar una comprobación previa. Para la toma definitiva, usar un entorno nuevo: no reutilizar datos de la comprobación y presentarlos como recién creados.

No fijar de antemano un número de tests aprobados. Leer el conteo de la ejecución real y distinguir aprobados, fallidos y omitidos.

## Recorrido de grabación

| Tiempo orientativo | Responsable | Acción en pantalla | Título breve | Evidencia visible |
|---|---|---|---|---|
| 0:00–0:20 | Ambos | Mostrar nombre del proyecto, SHA y matriz de requisitos | `Tarea 7 · Calidad de Thread Service` | Servicio, contrato e integración identificados; Isaías y Andrés con sus responsabilidades |
| 0:20–0:40 | Isaías | Abrir las rutas POST/GET de replies y GET de salud; mostrar su correspondencia con los tests | `Pruebas por endpoint` | Caso válido y caso negativo por operación; particularidad de salud explícita |
| 0:40–1:10 | Isaías | Mostrar la fixture de Mongo de pruebas, repositorio real, inyección y teardown | `Datos aislados por prueba` | Cliente/colección nuevos por caso, dependencias sustituidas y limpieza; ninguna URL de BD real |
| 1:10–1:40 | Isaías | Ejecutar la suite de servicio; mostrar un caso de creación y uno de contenido o referencia inválida | `Éxito y rechazo sin escrituras` | 201 en éxito; 422/404 en rechazo; aserciones sobre respuestas y outbox sin cambios |
| 1:40–2:00 | Isaías | Ejecutar de nuevo los casos de aislamiento y mostrar GET de raíz ausente y salud | `Ejecuciones independientes` | Estado inicial vacío; GET 404; salud 200 y método no permitido 405, correctamente explicado |
| 2:00–2:25 | Andrés | Mostrar revisión del proveedor y expectativas independientes de Users/Messages | `Contratos con el chat base` | Método, ruta, códigos y campos mínimos; proveedor real fijado y persistencia sustituida |
| 2:25–2:55 | Andrés | Ejecutar contratos: respuesta válida, inexistente y forma incompatible | `Compatibilidad verificada` | Aceptación de contrato válido; rechazo de ID numérico/campo requerido ausente; campos adicionales compatibles aceptados |
| 2:55–3:20 | Andrés | Mostrar configuración y estado del proyecto Compose QA | `Integración en Docker Compose` | Users, Channels, Messages y Threads reales; Mongo y Rabbit propios; red `microsvcs` |
| 3:20–4:10 | Andrés | Ejecutar el flujo que crea usuarios, canal, mensaje y respuesta por REST | `Andrés e Isaías · Grupo de estudio` | Estados HTTP, IDs obtenidos de respuestas y relaciones de la respuesta de Isaías con el mensaje de Andrés |
| 4:10–4:35 | Andrés | Mostrar GET de replies y GET de Messages; ejecutar los negativos del flujo | `Una respuesta pertenece a su raíz` | Respuesta listada una vez y ausente de mensajes raíz; 422/404 en casos inválidos; lista sin nuevos registros |
| 4:35–5:00 | Andrés | Reiniciar solo Threads del proyecto QA; esperar salud y consultar nuevamente | `Persistencia tras reinicio` | Mismo ID, contenido, canal, mensaje y autor recuperados por HTTP |
| 5:00–5:25 | Ambos | Mostrar segunda ejecución independiente, reportes por nivel y SHA integrado | `Resultados reproducibles` | Resultados actuales y separación entre tests de servicio, contrato e integración |
| 5:25–5:45 | Ambos | Limpiar solo el proyecto QA y mostrar enlaces a PR e instrucciones | `Evidencias y cierre` | Recursos propios limpiados; red compartida conservada; reportes sanitizados y comandos de reproducción |

Si la implementación del runner ejecuta el flujo completo de una vez, mostrar sus pasos conforme se imprimen y luego abrir el reporte. No detenerlo ni volver a enviar mutaciones manualmente para simular etapas separadas.

## Qué mostrar en cada bloque

### Isaías: servicio y aislamiento

Abrir `tests/test_qa_service.py` y `tests/qa_fixtures.py`, una vez implementados. Mostrar la preparación y limpieza, no solamente la salida verde de pytest.

Seleccionar estos ejemplos:

- POST válido: respuesta 201, contenido normalizado y lectura posterior.
- POST inválido: contenido vacío o autor inexistente; no aparecen documentos ni eventos nuevos.
- GET válido: lista vacía para raíz existente o respuesta almacenada correctamente.
- GET inválido: raíz inexistente devuelve 404; no confundirlo con una lista vacía.
- Salud: GET 200 y POST 405. Indicar con un rótulo: `405: método no permitido; liveness no consulta la BD`. No describirlo como una caída de GET /health ni un error de almacenamiento.

Comando previsto, que se debe confirmar después de implementar:

```sh
python -m pytest -q -W error tests/test_qa_service.py --junitxml=docs/tarea7/evidencias/servicio.xml
```

Repetir la suite o los casos de independencia. Dejar visible la aserción que verifica un estado nuevo por prueba. Un test que consulta una BD personal no sirve para demostrar aislamiento.

### Andrés: contratos

Abrir `tests/test_qa_contract.py`, el soporte de proveedor aislado y el lock de fuentes, una vez implementados. Mostrar:

- Users: `GET /api/v1/users/{id}`, respuesta 200 con ID string coincidente y 404 para inexistente.
- Messages: `GET /api/v1/channels/{channel_id}/messages`, respuesta lista con `id` y `channel_id` strings. Una lista sin la raíz devuelve falso en el cliente.
- Las rutas reales del proveedor se verifican en proceso, con su persistencia sustituida antes de importar. No hay Docker, acceso de red ni lectura de BD real durante estos tests.
- Las expectativas no se derivan únicamente del mismo modelo que se intenta probar. El consumidor rechaza un formato incompatible y acepta campos adicionales que no utiliza.

Comando previsto:

```sh
python integration/qa/run.py contract --directory <DIRECTORIO_QA_EXTERNO>
```

Una prueba negativa del contrato aparece como **aprobada** cuando comprueba que el consumidor rechaza la respuesta inválida. No introducir una rotura en producción para obtener una pantalla roja. No afirmar que existe un pacto verificado en el CI docente si solo se ejecutó verificación local sobre una revisión fijada.

### Andrés: integración

Comando previsto:

```sh
python integration/qa/run.py integration --directory <DIRECTORIO_QA_EXTERNO>
```

Mostrar resultados reales de estas operaciones, siguiendo los nombres implementados por el runner:

| Operación | Datos de demostración | Resultado que debe verse |
|---|---|---|
| Crear usuarios | `display_name: Andrés` y `display_name: Isaías` | 201 y un ID por usuario |
| Crear canal | `name: Grupo de estudio` | 201 e ID del canal |
| Crear mensaje | Andrés: `¿Nos juntamos mañana para repasar integrales?` | 201 e ID de mensaje raíz |
| Crear respuesta | Isaías: `¡Sí! Puedo a las cinco, después de clases.` | 201 e ID de respuesta vinculado al canal y a la raíz |
| Consultar replies | Canal y raíz creados | Respuesta con el mismo ID y contenido |
| Consultar Messages | Canal creado | Mensaje raíz presente; respuesta de Threads no agregada como mensaje raíz |
| Rechazar autor inexistente | Referencia inexistente de prueba | 422 y ningún reply nuevo |
| Rechazar raíz inexistente o de otro canal | Referencia inexistente o segundo canal real | 404 y ningún reply nuevo |
| Reiniciar Threads y releer | Mismos IDs de la demostración | Mismo reply persistido, recuperado por HTTP |

Los nombres y textos son naturales; los IDs técnicos se conservan en las respuestas como evidencia de las relaciones. No inventarlos ni recuperarlos accediendo directamente a Mongo de otro servicio.

Si se usa la copia docente corregida, dejar visible un rótulo: `Fuentes fijadas · copia local de prueba · parche de serialización documentado`. Mostrar el reporte de hashes y diff brevemente. No afirmar que la fuente original sin parche pasó si no fue así.

El evento publicado por el worker se muestra únicamente si se implementó su comprobación con cola temporal y correlación. Si no se implementa esa ampliación, el video acredita el flujo REST obligatorio sin atribuirle validación del broker.

## Cierre y verificación de la grabación

El cierre muestra `docs/tarea7/evidencias/resumen.md` y los reportes reales por nivel. Evitar abrir toda la configuración del entorno. La interfaz gráfica del chat puede aparecer como contexto opcional, pero no reemplaza las pruebas de QA de esta tarea.

Antes de compartir el video:

- [ ] El video corresponde al mismo SHA que los reportes mostrados.
- [ ] Se ven comandos ejecutados y resultados, no solo archivos de pruebas.
- [ ] Se distingue BD simulada en servicio/contrato de BD real exclusiva de QA en integración.
- [ ] Se ven los tres proveedores del chat y la capacidad Threads en Docker Compose.
- [ ] El reinicio mostrado corresponde al proyecto QA y la lectura posterior usa los mismos IDs.
- [ ] No se presentan skips como éxitos ni un 500 externo como creación correcta.
- [ ] No aparecen secretos ni datos ajenos.
- [ ] El MP4 se reproduce completo, los textos se leen y no hay narración, según la preferencia acordada.
- [ ] Los cortes de esperas están identificados y no sustituyen resultados reales por respuestas simuladas.
- [ ] Se agrega el enlace del video solo después de publicarlo por el medio de entrega autorizado.

**Video de Tarea 7: pendiente de grabar después de implementar y validar las pruebas.**
