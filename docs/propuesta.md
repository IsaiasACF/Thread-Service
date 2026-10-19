# Propuesta de capacidad — Threads de mensajes

## 1. Problema de usuario y contexto

Actualmente el chat permite publicar mensajes dentro de un canal, pero no permite responder directamente a un mensaje específico. Esto hace que conversaciones paralelas sobre distintos temas se mezclen en el flujo principal.

Se propone implementar un **Thread Service** que permita responder a un mensaje existente y consultar las respuestas asociadas a ese mensaje.

Ejemplo:

```text
Mensaje raíz:
"¿Cuándo es la entrega?"

Thread:
- "El viernes"
- "Antes de las 23:59"
```

La primera versión tendrá threads de un solo nivel: un mensaje raíz puede tener múltiples respuestas, pero no se permitirán respuestas anidadas a otras respuestas.

---

## 2. Lenguaje ubicuo y frontera de responsabilidad

Los conceptos principales serán:

- **Thread:** conversación asociada a un mensaje raíz.
- **Mensaje raíz:** mensaje del chat sobre el cual se inicia una conversación.
- **Respuesta:** contenido publicado dentro de un thread.
- **Autor:** usuario que crea una respuesta.

La responsabilidad del **Thread Service** será administrar los threads y sus respuestas.

El servicio no será responsable de crear usuarios, canales ni mensajes del chat base. Tampoco accederá directamente a las bases de datos de `users`, `channels` o `messages`. Las referencias externas se mantendrán mediante sus IDs y se utilizarán únicamente los contratos públicos del núcleo.

El Thread Service tendrá su propia persistencia para almacenar las respuestas y su relación con el mensaje raíz.

---

## 3. Diagrama de arquitectura

```text
                         CHAT BASE

┌─────────────────┐
│  Users Service  │
└────────▲────────┘
         │
         │ GET /api/v1/users/{user_id}
         │ Request-response sincrónico
         │
┌────────┴─────────┐
│  Thread Service  │───────────────┐
│                  │               │
│ Threads          │               ▼
│ Replies          │        ┌───────────────┐
└────────┬─────────┘        │ Threads DB    │
         │                  │ (propia)      │
         │                  └───────────────┘
         │
         │ GET /api/v1/channels/{channel_id}/messages
         │ Request-response sincrónico
         ▼
┌──────────────────┐
│ Messages Service │
└──────────────────┘

┌──────────────────┐
│ Channels Service │
└──────────────────┘
```

`Users`, `Channels` y `Messages` continúan siendo dueños de sus datos. El nuevo servicio solo mantiene información propia de los threads.

---

## 4. APIs y eventos

### APIs publicadas por Thread Service

Crear una respuesta a un mensaje:

```http
POST /api/v1/channels/{channel_id}/messages/{message_id}/replies
```

Body:

```json
{
  "author_id": "user-123",
  "content": "La entrega es el viernes"
}
```

Consultar las respuestas de un mensaje:

```http
GET /api/v1/channels/{channel_id}/messages/{message_id}/replies
```

### APIs consumidas

Validar que el mensaje raíz exista dentro del canal:

```http
GET /api/v1/channels/{channel_id}/messages
```

**Patrón:** request-response sincrónico mediante REST.

Validar que el autor exista:

```http
GET /api/v1/users/{user_id}
```

**Patrón:** request-response sincrónico mediante REST.

No se accederá directamente a las bases de datos de los servicios base.

### Evento publicado

Cuando se crea correctamente una respuesta:

```text
chat.thread.reply.created
```

**Patrón:** event-driven asíncrono.

El evento podrá informar al menos el identificador de la respuesta, el mensaje raíz, el canal y el autor. El Thread Service publica el evento sin depender de qué otros servicios puedan consumirlo posteriormente.

---

## 5. Flujo de usuario de punta a punta

```text
1. Se crea un usuario.
        ↓
2. Se crea un canal.
        ↓
3. Se publica un mensaje en el canal.
        ↓
4. Otro usuario selecciona el mensaje y escribe una respuesta.
        ↓
5. Thread Service comprueba mediante las APIs públicas
   que el mensaje raíz y el autor existen.
        ↓
6. Thread Service guarda la respuesta en su propia base de datos.
        ↓
7. Se publica el evento chat.thread.reply.created.
        ↓
8. El usuario consulta el thread del mensaje.
        ↓
9. Thread Service devuelve las respuestas asociadas.
```

Ejemplo de demostración final:

```text
Mensaje raíz:
"¿A qué hora empieza la reunión?"

Respuestas:
- "A las 10:00"
- "Será por Teams"
```

---

## Decisiones de diseño

- El servicio mantiene **alta cohesión** al concentrar únicamente la funcionalidad de threads.
- Se evita **acoplamiento común y de contenido**, ya que no comparte ni accede a las bases de datos del núcleo.
- Las referencias a usuarios y mensajes se realizan mediante sus IDs.
- Las validaciones necesarias utilizan **request-response sincrónico**, porque el resultado se necesita antes de aceptar una respuesta.
- El evento `chat.thread.reply.created` utiliza comunicación **event-driven**, permitiendo que futuras capacidades reaccionen a una respuesta sin aumentar el acoplamiento del Thread Service.
