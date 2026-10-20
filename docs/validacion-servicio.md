## 1. Levantar servicios

Corregir la base, ya que las entidades no se guardan correctamente en sus respectivas BDD, modificando el POST de cada servicio, al hacer uso de insert_one (cambios: users.insert_one(user.copy()), messages.insert_one(message.copy()), channels.insert_one(channel.copy()))

Configurar la sesión levantando los servicios base (usando el compose entregado en el curso) y levantando el thread service mediante el [docker-compose](../docker-compose.yaml).

Consultar la salud de los cuatro servicios:

```powershell
$ErrorActionPreference = 'Stop'
$usersUrl = 'http://localhost:8001'
$channelsUrl = 'http://localhost:8002'
$messagesUrl = 'http://localhost:8003'
$threadsUrl = 'http://localhost:8004'

Invoke-RestMethod "$usersUrl/health"
Invoke-RestMethod "$channelsUrl/health"
Invoke-RestMethod "$messagesUrl/health"
Invoke-RestMethod "$threadsUrl/health"
```

Swagger de Threads: http://localhost:8004/docs para ver endpoints.

## 2. Crear un usuario

```powershell
$resultadoUsuario = Invoke-WebRequest -UseBasicParsing `
  -Method Post -Uri "$usersUrl/api/v1/users" `
  -ContentType 'application/json' `
  -Body (@{ display_name = 'Demo Threads' } | ConvertTo-Json)

$resultadoUsuario.StatusCode
$usuario = $resultadoUsuario.Content | ConvertFrom-Json
$usuario | ConvertTo-Json -Depth 5
if (-not $usuario.id) { throw 'Users no devolvio un id' }
```

**Resultado esperado:** HTTP `201` y un objeto con `id`.

## 3. Crear un canal

```powershell
$resultadoCanal = Invoke-WebRequest -UseBasicParsing `
  -Method Post -Uri "$channelsUrl/api/v1/channels" `
  -ContentType 'application/json' `
  -Body (@{ name = 'demo-threads' } | ConvertTo-Json)

$resultadoCanal.StatusCode
$canal = $resultadoCanal.Content | ConvertFrom-Json
$canal | ConvertTo-Json -Depth 5
if (-not $canal.id) { throw 'Channels no devolvio un id' }
```

**Resultado esperado:** HTTP `201` y el ID del canal.

## 4. Crear un mensaje raíz

Publica un mensaje en el canal con el usuario creado:

```powershell
$mensajesDelCanalUrl = "$messagesUrl/api/v1/channels/$($canal.id)/messages"
$resultadoMensaje = Invoke-WebRequest -UseBasicParsing `
  -Method Post -Uri $mensajesDelCanalUrl `
  -ContentType 'application/json' `
  -Body (@{
    author_id = $usuario.id
    content = 'Mensaje raiz de la demostracion'
  } | ConvertTo-Json)

$resultadoMensaje.StatusCode
$mensaje = $resultadoMensaje.Content | ConvertFrom-Json
$mensaje | ConvertTo-Json -Depth 5
if (-not $mensaje.id) { throw 'Messages no devolvio un id' }

Invoke-RestMethod $mensajesDelCanalUrl | ConvertTo-Json -Depth 5
```

**Resultado esperado:** HTTP `201`.

Ya existe un mensaje raíz en Messages. Threads consulta ese servicio para validar que el mensaje pertenece al canal y consulta Users para validar al autor de cada respuesta.

## 5. Consultar el hilo vacío

```powershell
$hiloUrl = "$threadsUrl/api/v1/channels/$($canal.id)/messages/$($mensaje.id)/replies"
$consulta = Invoke-WebRequest -UseBasicParsing -Uri $hiloUrl
$consulta.StatusCode
$consulta.Content
```

**Resultado esperado:** HTTP `200` y `[]`. El mensaje existe, pero todavía no tiene respuestas.

## 6. Crear la primera respuesta

Publicar una respuesta en Threads:

```powershell
$resultadoRespuesta = Invoke-WebRequest -UseBasicParsing `
  -Method Post -Uri $hiloUrl `
  -ContentType 'application/json' `
  -Body (@{
    author_id = $usuario.id
    content = 'Primera respuesta de la demostracion'
  } | ConvertTo-Json)

$resultadoRespuesta.StatusCode
$respuesta = $resultadoRespuesta.Content | ConvertFrom-Json
$respuesta | ConvertTo-Json -Depth 5
if (-not $respuesta.id) { throw 'Threads no devolvio un id' }
```

**Resultado esperado:** HTTP `201` y estos campos:

| Campo | Qué comprobar |
|---|---|
| `id` | ID generado para la respuesta |
| `channel_id` | Coincide con `$canal.id` |
| `message_id` | Coincide con `$mensaje.id` |
| `author_id` | Coincide con `$usuario.id` |
| `content` | Contiene el texto enviado |
| `created_at` | Fecha y hora en UTC |

## 7. Agregar otra respuesta y consultar el hilo

Crear una segunda respuesta al mismo mensaje:

```powershell
$segundaRespuesta = Invoke-RestMethod `
  -Method Post -Uri $hiloUrl `
  -ContentType 'application/json' `
  -Body (@{
    author_id = $usuario.id
    content = 'Segunda respuesta de la demostracion'
  } | ConvertTo-Json)

$lista = @(Invoke-RestMethod -Uri $hiloUrl)
$lista | ConvertTo-Json -Depth 5
if ($lista.Count -ne 2) { throw 'Se esperaban dos respuestas' }
if ($respuesta.id -notin $lista.id) { throw 'Falta la primera respuesta' }
if ($segundaRespuesta.id -notin $lista.id) { throw 'Falta la segunda respuesta' }
'OK: ambas respuestas aparecen en el hilo'
```

**Resultado esperado:** dos respuestas ordenadas por fecha e ID, con IDs propios y el mismo `message_id`.

## 8. Comprobar el evento en RabbitMQ

1. Abrir [RabbitMQ Management](http://localhost:15672).
2. Iniciar sesión con usuario `threads` y contraseña `threads`, si conservas la configuración del repositorio.
3. Abrir **Queues and Streams** y seleccionar `thread.reply.created`.
4. Expandir **Get messages** y seleccionar la opción de reencolar los mensajes (**Ack mode: Nack message requeue true**, según la versión de la interfaz).
5. Solicitar mensajes y buscar el evento de la respuesta creada. 

Compara el evento con el ID que muestra este comando:

```powershell
$respuesta.id
```

**Resultado esperado:** un evento con `type` igual a `chat.thread.reply.created`, `subject_id` igual a `$respuesta.id` y `data` con el contenido de esa respuesta. Debe existir también un evento para la segunda respuesta.

Si no aparece, esperar unos segundos y revisar el worker:

```powershell
docker compose logs --tail=100 worker
```

La API guarda la respuesta junto con un evento pendiente en MongoDB. El worker publica ese evento en RabbitMQ y lo marca como publicado después de la confirmación del broker. El HTTP 201 confirma persistencia; la publicación ocurre de forma asíncrona.

RabbitMQ de este Compose pertenece a Threads. Esta prueba demuestra la publicación en su broker, no demuestra que otro microservicio consuma el evento.

## 9. Comprobar validaciones (opcional)

Define esta función para mostrar también los errores HTTP sin detener la demostración. Funciona con Windows PowerShell 5.1 y PowerShell 7:

```powershell
function Test-ErrorHttp {
  param(
    [string]$Uri,
    [string]$Method = 'Get',
    [string]$Body,
    [int]$Esperado
  )
  $parametros = @{
    Uri = $Uri
    Method = $Method
    UseBasicParsing = $true
    ErrorAction = 'Stop'
  }
  if ($Method -eq 'Post') {
    $parametros.ContentType = 'application/json'
    $parametros.Body = $Body
  }
  try {
    $resultado = Invoke-WebRequest @parametros
    throw "Se esperaba HTTP $Esperado, pero llego $($resultado.StatusCode)"
  } catch {
    if ($null -eq $_.Exception.Response) { throw }
    $codigo = [int]$_.Exception.Response.StatusCode
    "HTTP recibido: $codigo | esperado: $Esperado"
    $_.ErrorDetails.Message
    if ($codigo -ne $Esperado) { throw }
  }
}
```

### 9.1. Rechaza contenido vacío

Enviar contenido formado por espacios:

```powershell
Test-ErrorHttp -Uri $hiloUrl -Method Post -Esperado 422 -Body (@{
  author_id = $usuario.id
  content = '   '
} | ConvertTo-Json)
```

**Resultado esperado:** HTTP `422` con un error de validación del contenido.

### 9.2. Rechaza un autor inexistente

Generar un ID aleatorio y usarlo como autor:

```powershell
$autorInexistente = [guid]::NewGuid().ToString()
Test-ErrorHttp -Uri $hiloUrl -Method Post -Esperado 422 -Body (@{
  author_id = $autorInexistente
  content = 'Esta respuesta debe ser rechazada'
} | ConvertTo-Json)
```

**Resultado esperado:** HTTP `422` y `Author does not exist`, si Users devuelve `404` para el ID inexistente como exige el contrato.

### 9.3. Rechaza un mensaje inexistente

Consultar un hilo donde mensaje raíz no existe:

```powershell
$mensajeInexistente = [guid]::NewGuid().ToString()
$hiloInexistenteUrl = "$threadsUrl/api/v1/channels/$($canal.id)/messages/$mensajeInexistente/replies"
Test-ErrorHttp -Uri $hiloInexistenteUrl -Esperado 404
```

**Resultado esperado:** HTTP `404` y `Root message not found in channel`.

### 9.4. Confirmar que los errores no guardaron respuestas

Consultar nuevamente el hilo válido:

```powershell
$lista = @(Invoke-RestMethod -Uri $hiloUrl)
if ($lista.Count -ne 2) { throw 'Las validaciones alteraron el hilo' }
'OK: el hilo conserva sus dos respuestas'
```

## 10. Comprobar persistencia después de reiniciar (opcional)

Reiniciar la API, el worker y MongoDB de Threads:

```powershell
docker compose restart mongodb threads worker
```

Espera a que MongoDB y la API vuelvan a estar disponibles. Puedes consultar el estado con:

```powershell
docker compose ps
Invoke-RestMethod "$threadsUrl/health"
```

Consultar el hilo y compara los IDs:

```powershell
$persistidas = @(Invoke-RestMethod -Uri $hiloUrl)
$persistidas | ConvertTo-Json -Depth 5
if ($respuesta.id -notin $persistidas.id) { throw 'Falta la primera respuesta tras reiniciar' }
if ($segundaRespuesta.id -notin $persistidas.id) { throw 'Falta la segunda respuesta tras reiniciar' }
'OK: las respuestas siguen guardadas despues del reinicio'
```

**Resultado esperado:** ambas respuestas conservan sus IDs y contenido.


### Consultar el [README](../README.md) y los [contratos del servicio](contracts.md) para revisar la configuración y los límites de la API.
