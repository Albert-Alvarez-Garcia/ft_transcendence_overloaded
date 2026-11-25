# Salas de juego: contrato WebSocket

Capa genérica y reutilizable para cualquier proceso multiusuario (juegos, salas colaborativas…).
Código: `backend/game_rooms.py` (lógica), `backend/routers/rooms.py` (HTTP y WebSocket), `backend/games/` (juegos).
El contrato HTTP de las salas está en [`API.md`](API.md). Quien cambie un mensaje actualiza este fichero en el mismo cambio.

## Conexión
`wss://localhost:8443/ws/rooms/{code}` — requiere la cookie de sesión y que `Origin` coincida con el host.
Antes de abrir el WebSocket, el cliente debe comprobar que la sala existe con `GET /api/rooms/{code}` (así no hay errores de conexión en la consola).

El servidor acepta la conexión y, si algo falla, la cierra con un código:

| Código | Significado |
|---|---|
| `4401` | Sin sesión, o sesión cerrada |
| `4403` | Origen no permitido |
| `4404` | La sala no existe o ha caducado |
| `4409` | Sustituida por otra conexión del mismo usuario (otra pestaña) |
| `4410` | La partida ya ha empezado y no eras jugador |
| `4411` | Sala llena |

## Ciclo de vida de una sala
```
lobby ──(el anfitrión envía start)──> playing ──(el juego llama a finish)──> finished
                                         ^                                      │
                                         └──────(el anfitrión envía start)──────┘   "jugar otra vez"
```
- **Crear:** `POST /api/rooms`. El código tiene 5 caracteres. Si nadie entra en 60 s, la sala se elimina sola.
- **Anfitrión:** quien crea la sala. Si sale en el lobby, pasa al siguiente jugador.
- **Empezar:** solo el anfitrión, y con al menos `minPlayers` jugadores conectados. Al empezar se retira a los desconectados.
- **Entrar tarde:** una vez empezada, solo pueden volver los que ya eran jugadores (reconexión). Los demás reciben `4410`.
- **Reconexión:** si un jugador se desconecta en mitad de la partida conserva su sitio; al volver recibe un `room_state` completo.
- **Sala vacía:** en el lobby se elimina al salir el último. En partida se espera 60 s por si alguien vuelve.

## Cliente → servidor
Todos los mensajes son JSON con un campo `type`. Máximo 4096 caracteres.

| `type` | Campos | Quién | Efecto |
|---|---|---|---|
| `start` | — | Anfitrión | Empieza (o repite) la partida |
| `chat` | `text` (máx. 300) | Cualquiera | Mensaje a toda la sala. Límite: 5 cada 3 s |
| `game` | `action` + campos del juego | Jugadores, solo en `playing` | Se entrega al juego (`on_message`) |
| `leave` | — | Cualquiera | Sale y cierra la conexión |

## Servidor → cliente
| `type` | Campos | Cuándo |
|---|---|---|
| `room_state` | `code, game, phase, endsAt, hostId, you{id,username}, players[], settings, minPlayers, maxPlayers, gameState` | Al entrar, al reconectar y al empezar. Es una foto completa: sustituye al estado del cliente |
| `player_joined` | `player{id,username,connected,isHost}` | Entra un jugador nuevo |
| `player_left` | `id, hostId` | Sale un jugador en el lobby |
| `player_status` | `id, connected` | Se (des)conecta un jugador en partida |
| `phase` | `phase, endsAt` | Cambia la fase (`endsAt` en milisegundos desde 1970, o `null`) |
| `chat` | `user, text, ts` | Mensaje de chat |
| `game` | `action` + campos del juego | Lo envía el juego a la sala |
| `finished` | `results[{userId, username, score, rank}]` | Fin de partida |
| `error` | `code` | Error no fatal. Códigos: `not_host`, `not_enough_players`, `already_started`, `not_playing`, `too_fast`, `too_large`, `bad_message`, `unknown_type` |

Los identificadores de jugador usados como clave de un objeto JSON llegan como texto (`"3"`), no como número.

## Juego de demostración: `demo_race`
Gana quien llegue antes al número de clics objetivo (`settings.target`, 10 por defecto; 2 a 4 jugadores).
- Cliente → servidor: `{"type": "game", "action": "click"}`
- Servidor → cliente: `{"type": "game", "action": "progress", "clicks": {"<userId>": n}}`
- `gameState` en `room_state`: `{"clicks": {...}, "target": 10}`

## Cómo añadir un juego
1. Copia `backend/games/demo_race.py` con otro nombre y cambia `id`, `name`, `min_players` y `max_players`.
2. Implementa los hooks que necesites (todos opcionales): `default_settings`, `on_start`, `on_message`, `on_leave`, `on_rejoin` y `snapshot`.
3. Importa el módulo en `backend/games/__init__.py` para que se registre.
4. Documenta aquí sus mensajes `game` (acciones, campos y `gameState`).
5. Añade pruebas en `tests/`.

API de `room` disponible dentro de un juego:

| Elemento | Uso |
|---|---|
| `room.players` | Diccionario `user_id → Player` (`username`, `connected`) |
| `room.settings` | Ajustes de la partida (`default_settings` fusionado con lo que envió el cliente) |
| `room.data` | Diccionario libre para el estado del juego |
| `await room.broadcast(type, **campos)` | Envía a todos |
| `await room.send(player, type, **campos)` | Envía solo a uno (por ejemplo, la palabra secreta) |
| `await room.set_phase(fase, ends_at)` | Cambia la fase y avisa. Las cuentas atrás usan `endsAt` absoluto, no un mensaje por segundo |
| `await room.finish(results)` | Cierra la partida, avisa y llama a `record_match` |

Reglas de diseño: el **servidor manda** (el cliente envía intenciones y pinta lo que recibe), la información privada se envía solo a quien le corresponde, y `snapshot` debe devolver todo lo necesario para pintar el juego desde cero (reconexión).

## Guardado de partidas
`backend/routers/rooms.py` define `record_match(game_id, code, results)`, que hoy solo escribe en el log. Quien sea dueño de la tabla de partidas lo implementará (el estado de la partida en curso nunca se guarda).

## Limitaciones conocidas (aceptadas)
Estas limitaciones son una decisión consciente para este proyecto y están aquí para que quede constancia:
1. **Las salas viven solo en la memoria del backend.** Si el backend se reinicia (`make restart`, `make up` tras un cambio, una caída), todas las salas y partidas en curso se pierden. Los clientes ven cerrarse la conexión y vuelven al lobby.
2. **Solo funciona con un proceso del backend.** No se debe arrancar `uvicorn` con `--workers` mayores que 1 ni con varias réplicas: cada proceso tendría sus propias salas. Escalar exigiría un almacén compartido (por ejemplo Redis) y no está previsto.
3. **El estado de una partida en curso no se guarda en la base de datos.** Solo se guardan los resultados finales, y solo cuando `record_match` los guarda.
4. **Tiempo de gracia fijo de 60 s** para reconectar a una partida en curso. Pasado ese tiempo sin jugadores conectados, la sala se elimina.
5. **Si el anfitrión se desconecta durante la partida,** nadie más puede reiniciarla hasta que vuelva (al terminar, el siguiente `start` retira a los desconectados).
6. **Las salas abiertas son públicas** y el código de sala no es un secreto. No hay contraseñas ni salas privadas.
7. **Límites:** 200 salas a la vez, 4096 caracteres por mensaje y 5 mensajes de chat cada 3 segundos.
8. **Sin espectadores** y sin reintento ni confirmación de entrega más allá de lo que da TCP.
