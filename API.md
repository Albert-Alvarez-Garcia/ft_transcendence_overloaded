# Contrato de la API

Base: `https://localhost:8443`. Formato: JSON. Autenticación: cookie `cb_session` (la pone el servidor; el navegador la envía sola).

## Convenciones
- **Los resultados esperados siempre devuelven HTTP 200.** El resultado va en el cuerpo:
  - éxito: `{"ok": true, ...}`
  - error esperado: `{"ok": false, "error": "<codigo>"}`
- Las peticiones que cambian datos (`POST`, `PUT`, `DELETE`) comprueban la cabecera `Origin`. Si no coincide con el host: **HTTP 403** (solo ocurre en un ataque o en una llamada de otro origen).
- Un fallo inesperado del servidor devuelve 5xx. Cuerpos sin JSON válido no son un caso soportado.
- Todas las respuestas llevan `Cache-Control: no-store`.

## Códigos de error
| Código | Significado |
|---|---|
| `invalid_username` | 3-20 caracteres: letras, números, `_` y `-` |
| `invalid_email` | Formato de correo no válido |
| `invalid_password` | Entre 8 y 72 caracteres |
| `username_taken` / `email_taken` | Ya existe |
| `email_failed` | No se pudo enviar el correo de confirmación |
| `invalid_credentials` | Usuario o contraseña incorrectos |
| `not_verified` | Falta confirmar el correo |
| `too_many_attempts` | Límite de intentos superado |
| `invalid_or_expired` | Token de confirmación inválido o caducado |
| `unauthenticated` | No hay sesión válida |
| `already_exists` / `not_created` | Estado incorrecto en `/api/test` |

Límites por IP: login 10 intentos / 5 min · registro 5 / 10 min · reenvío de correo 3 / 10 min.

## Sistema
### `GET /api/health`
`200` → `{"ok": true}`

## Autenticación
### `GET /api/auth/me`
Sin sesión: `{"authenticated": false}`. Con sesión: `{"authenticated": true, "user": {"username": "...", "email": "..."}}`

### `POST /api/auth/register`
Cuerpo: `{"username": "", "email": "", "password": ""}`
Éxito: `{"ok": true}` (se envía el correo de confirmación). Errores: `invalid_username`, `invalid_email`, `invalid_password`, `username_taken`, `email_taken`, `too_many_attempts`, `email_failed` (en este caso el usuario no se crea).

### `POST /api/auth/verify-email`
Cuerpo: `{"token": ""}` (el token viaja en el enlace del correo: `/verify.html?token=...`)
Éxito: `{"ok": true}`. Error: `invalid_or_expired`.

### `POST /api/auth/resend-verification`
Cuerpo: `{"email": ""}`. Siempre `{"ok": true}` exista o no la cuenta (no revela qué correos están registrados). Errores: `too_many_attempts`, `email_failed`.

### `POST /api/auth/login`
Cuerpo: `{"identifier": "usuario o correo", "password": ""}`
Éxito: `{"ok": true, "user": {"username": "..."}}` + `Set-Cookie: cb_session` (`HttpOnly; Secure; SameSite=Lax`). Se registra una sesión (IP, navegador, fecha).
Errores: `invalid_credentials`, `not_verified`, `too_many_attempts`.

### `POST /api/auth/logout`
Sin cuerpo. Siempre `{"ok": true}`. Cierra la sesión en base de datos, borra la cookie y corta las conexiones del chat de esa sesión.

### `GET /api/auth/42/login` → `302`
Redirige a 42 para autorizar. Si faltan credenciales: `302 /login.html?error=oauth_unavailable`.

### `GET /api/auth/42/callback` → `302`
Éxito: `302 /home.html` con la cookie de sesión. Fallo: `302 /login.html?error=oauth_failed`.
La URL registrada en la aplicación de 42 debe ser exactamente `{PUBLIC_BASE_URL}/api/auth/42/callback`.

## Test API (requiere sesión)
Opera sobre `users.test`: `null` (no creado), `true` o `false`. Sin sesión: `{"ok": false, "error": "unauthenticated"}`.

| Método | Ruta | Acción | Éxito | Errores |
|---|---|---|---|---|
| `GET` | `/api/test` | Consultar | `{"ok": true, "value": null\|true\|false}` | — |
| `POST` | `/api/test` | Crear | `value: true` | `already_exists` |
| `PUT` | `/api/test` | Modificar (alterna true/false) | `value: <nuevo>` | `not_created` |
| `DELETE` | `/api/test` | Borrar | `value: null` | `not_created` |

## Chat (WebSocket)
`wss://localhost:8443/ws/chat` — requiere la cookie de sesión y que `Origin` coincida con el host.

- **Cliente → servidor:** texto plano. Se recorta y se limita a 500 caracteres; los vacíos se ignoran.
- **Servidor → cliente (JSON):**
  - mensaje: `{"type": "message", "user": "...", "text": "...", "ts": 1700000000}`
  - aviso: `{"type": "system", "text": "..."}` (entradas, salidas y límite de velocidad)
- **Límite:** 5 mensajes cada 3 segundos por conexión; al superarlo llega un aviso `system`.
- **Cierre:** el servidor acepta la conexión y la cierra con código `4401` (sin sesión, o sesión cerrada) o `4403` (origen no permitido).
- La sala es única y global, y solo vive en memoria: no hay historial.

## Base de datos
- **`users`**: `id`, `username` (único sin distinguir mayúsculas), `email` (único), `password_hash` (NULL si solo usa 42), `email_verified`, `verify_token_hash`, `verify_expires`, `fortytwo_id`, `test`, `created_at`.
- **`sessions`**: `id` (UUID), `user_id`, `method` (`password`|`42`), `ip`, `user_agent`, `login_at`, `logout_at` (NULL = abierta, o caducada sin cerrar).
