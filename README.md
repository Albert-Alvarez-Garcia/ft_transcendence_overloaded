# transcendence_starter_pack

Base web segura y mínima para arrancar un proyecto: **FastAPI + PostgreSQL + nginx (HTTPS) + HTML/CSS/JS puros**, todo en Docker.
No es un proyecto terminado: es la parte que casi todos los proyectos necesitan, ya resuelta y documentada.
El contrato de la API está en [`docs/API.md`](docs/API.md).

## Qué incluye
- **Registro con confirmación por correo** (SMTP; probado con Gmail y contraseña de aplicación).
- **Login con usuario o correo**, y **login con 42** (OAuth2, sin descargar avatar).
- **Sesión en cookie** `HttpOnly` + `Secure` + `SameSite=Lax`, validada contra la base de datos. Sin `localStorage`.
- **Registro de sesiones**: usuario, método (`password`/`42`), IP, navegador, fecha de entrada y de salida.
- **Chat grupal** por WebSocket (una sala global, sin historial).
- **Página "Test API"**: CRUD mínimo sobre un campo `test` del usuario, como ejemplo de endpoint protegido.
- **HTTPS con certificado autofirmado**, redirección 8080 → 8443 y cabeceras de seguridad (CSP incluida).
- **Consola del navegador limpia**: los errores esperados responden HTTP 200 con `{"ok": false, "error": "..."}`.
- **Modo desarrollo** con recarga automática y correo falso (Mailpit), y una **prueba de humo** (`make smoke`).
- **Salas de juego genéricas** (WebSocket) con un juego de demostración y pruebas unitarias: base para cualquier juego o proceso multiusuario.

## Qué NO incluye (a propósito)
Panel de administración, historial del chat, recuperación de contraseña, 2FA, avatares, migraciones de esquema ni tests automáticos completos.

## Arranque
1. Copia `.env.example` a `.env` y rellénalo (nunca lo subas a git).
2. En tu aplicación de 42, registra la URL de retorno: `https://localhost:8443/api/auth/42/callback`.
3. `make dev` (desarrollo) o `make up` (entrega) y abre `https://localhost:8443`. Acepta el aviso del certificado autofirmado.

## Modo desarrollo y modo entrega
| | `make dev` | `make up` |
|---|---|---|
| Uso | Trabajar día a día | Entrega y evaluación |
| Backend | Se recarga solo al guardar | Código dentro de la imagen |
| Frontend | Se ve al refrescar el navegador | Copiado dentro de la imagen |
| Correo | **Mailpit**: bandeja en http://localhost:8025, no se envía nada real | SMTP real del `.env` |
| Configuración | `docker-compose.yml` + `docker-compose.dev.yml` | Solo `docker-compose.yml` |

Los archivos de `frontend/` y `backend/` necesitan permisos de lectura (`644`) para que los contenedores los lean.
Para pasar de un modo a otro: `make down` y luego el otro comando.

## Cómo funciona el Makefile
Todos los comandos se ejecutan **desde la raíz del proyecto**, con `make <comando>`. Cada uno lanza una secuencia fija de órdenes.

### `make up` / `make dev` — construir y arrancar
1. **Comprueba que existe `.env`.** Si falta, se detiene con el mensaje `Falta .env`.
2. **Genera el certificado** si no existe (ver `make certs`).
3. Ejecuta `docker compose up -d --build`: construye las imágenes, arranca Postgres y espera a que esté listo, arranca el backend y por último nginx. Lee `.env` automáticamente. Quedan en segundo plano (`-d`).
4. `make dev` añade `docker-compose.dev.yml`: monta tus carpetas, activa la recarga y levanta Mailpit.

Es seguro ejecutarlos varias veces: Docker solo reconstruye lo que ha cambiado.

### `make certs` — certificado autofirmado
Crea `certs/` y, **solo si faltan `cert.pem` o `key.pem`**, los genera con `openssl` (365 días, para `localhost` y `127.0.0.1`).
Para renovarlos: borra los dos archivos y ejecuta `make up`.

### `make down` — parar
Para y elimina los contenedores y la red, en cualquier modo. **Los datos se conservan** (volumen `pgdata`).

### `make restart` — reiniciar
`make down` seguido de `make up` (modo entrega).

### `make logs` / `make status`
`logs` muestra los logs en directo; `Ctrl+C` sale **sin parar los contenedores**. Para ver uno solo: `docker compose logs -f backend` (también `frontend`, `postgres_db`).
`status` lista los contenedores y si están en marcha.

### `make sessions` — sesiones registradas
Lanza una consulta dentro de Postgres: las últimas 20 sesiones (usuario, método, IP, entrada, salida, navegador). Necesita los contenedores arrancados.

### `make smoke` — prueba de humo
Ejecuta `scripts/smoke.sh` contra `https://localhost:8443`: comprueba salud, redirección a HTTPS, 404 reales, errores esperados con HTTP 200 y que no hay acceso sin sesión.
Para probar también la parte con sesión (crear, modificar y borrar en Test API, y logout), usa un usuario ya verificado:
```bash
SMOKE_USER=nombre SMOKE_PASS=clave make smoke
```
Termina con `Todo correcto` o con `Hay fallos` (y código de salida 1).

### `make clean` / `make re`
`clean` ejecuta `down -v`: **borra el volumen, es decir, todos los usuarios y sesiones**. No toca `certs/` ni `.env`.
`re` es `clean` + `up`. Úsalo después de cambiar `database/init.sql`.

### Qué ejecutar según lo que hayas cambiado
| Has cambiado… | En `make dev` | En `make up` |
|---|---|---|
| Código del backend | Nada: se recarga solo | `make up` |
| Páginas, CSS o JS | Refrescar el navegador | `make up` |
| `docker/nginx.conf` | `make dev` | `make up` |
| `.env` | `make down` y `make dev` | `make restart` |
| `database/init.sql` | `make re` (borra datos) | `make re` |

### Si algo falla
- **`Falta .env`:** copia tu `.env` a la raíz.
- **`port is already allocated` (8080 u 8443):** otro proyecto usa esos puertos. Páralo con su propio `make down`.
- **Aviso del certificado:** es normal. "Avanzado → Continuar".
- **La página no carga:** `make status` para ver los tres contenedores y, si falla alguno, `make logs`.
- **403 de nginx en `make dev`:** permisos de los archivos de `frontend/`: `chmod -R a+rX frontend`.

## Variables de entorno (`.env`)
| Variable | Para qué |
|---|---|
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | Base de datos |
| `DB_PASSWORD` | Debe ser igual que `POSTGRES_PASSWORD` |
| `JWT_SECRET` | Firma de la cookie de sesión. Obligatoria: sin ella el backend no arranca |
| `SESSION_TTL_HOURS` | Duración de la sesión (24 por defecto) |
| `PUBLIC_BASE_URL` | URL pública, p. ej. `https://localhost:8443`. Se usa en el enlace del correo y en el retorno de 42 |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | Correo real (con `make dev` se ignoran) |
| `FORTYTWO_CLIENT_ID`, `FORTYTWO_CLIENT_SECRET` | Login con 42 |

## Trabajo en equipo
- **Cada persona tiene su propio `.env`.** No se comparte por el repositorio. Los secretos comunes (como el `client_secret` de 42) se pasan por un canal privado.
- **Ramas y revisión:** cada cambio va en una rama y otra persona lo revisa. Regla de oro: `main` siempre arranca con `make up`.
- **Menos conflictos:** un router por funcionalidad y una página con su JS por vista. Los puntos calientes son `backend/main.py`, `database/init.sql` y `docs/API.md`.
- **El contrato manda:** quien cambia un endpoint actualiza su línea en `docs/API.md` en el mismo cambio.
- **Antes de subir cambios:** `make smoke`.
- **Formato común:** `.editorconfig` y `.gitattributes` evitan diferencias de sangrado y saltos de línea entre sistemas.

## Estructura
```
backend/            FastAPI
  main.py           arranque, routers y cabeceras
  config.py         lectura de variables de entorno
  db.py             pool de conexiones a Postgres
  security.py       contraseñas, token de sesión, límites, comprobación de Origin
  mailer.py         envío del correo de confirmación
  game_rooms.py     capa genérica de salas (sin dependencias de FastAPI)
  games/            un fichero por juego (demo_race.py es la plantilla)
  routers/          auth.py · test_api.py · chat.py · rooms.py
frontend/           páginas estáticas servidas por nginx
  *.html            login · verify · home · test-api
  css/main.css
  js/shared/api.js  cliente de la API (todas las páginas lo usan)
  js/pages/         un JS por página
database/init.sql   esquema: users, sessions
docker/             nginx.conf y Dockerfile de nginx
scripts/smoke.sh    prueba de humo
certs/              certificado autofirmado (se genera; no se versiona)
docs/API.md         contrato de la API (HTTP)
docs/WS.md          contrato de las salas de juego (WebSocket)
tests/              pruebas unitarias de las salas
docker-compose.yml       entrega
docker-compose.dev.yml   desarrollo (recarga + Mailpit)
```

## Salas de juego
Capa genérica: crear sala con código, lobby, anfitrión, fases (`lobby` → `playing` → `finished`), reconexión, chat de sala y gancho para guardar resultados.
Cada juego es un fichero en `backend/games/` que implementa unos pocos métodos. Todo está descrito en [`docs/WS.md`](docs/WS.md).

- Pantalla de prueba: `https://localhost:8443/rooms.html` (abre dos pestañas con usuarios distintos).
- Pruebas unitarias, sin Docker: `python3 -m unittest discover -s tests -t . -v`

## Limitaciones conocidas
Aceptadas de forma consciente (detalle completo en [`docs/WS.md`](docs/WS.md)):
- **Las salas y partidas en curso viven en la memoria del backend:** si se reinicia, se pierden. Solo se guardan los resultados finales, y solo si `record_match` los guarda.
- **Un solo proceso:** no usar `uvicorn --workers` mayor que 1 ni varias réplicas del backend.
- **Salas públicas y sin contraseña**, sin espectadores, 200 salas como máximo.
- Los límites de intentos de acceso también viven en memoria y se reinician con el backend.

## Seguridad: qué está resuelto
Contraseñas con bcrypt · cookie `HttpOnly`/`Secure`/`SameSite` · sesión revocable en base de datos ·
token de confirmación hasheado, con caducidad y de un solo uso · comprobación de `Origin` en peticiones que cambian datos y en el chat ·
límite de intentos en login, registro y reenvío · IP real fijada por nginx (no falsificable) · CSP estricta ·
Postgres y backend sin puertos publicados · backend sin root · sin contraseña para cuentas que solo usan 42.

## Seguridad: qué falta antes de producción
Fijar versiones de dependencias · certificado válido y HSTS · límites de intentos fuera de memoria (Redis o nginx) ·
registrar intentos fallidos · marcar como cerradas las sesiones caducadas · healthcheck del backend · migraciones.

## Cómo extender
- **Nuevo endpoint:** crea `backend/routers/<nombre>.py`, regístralo en `main.py` y sigue la convención: usar `current_session()`,
  llamar a `check_origin()` si cambia datos y devolver HTTP 200 con `{"ok": false, "error": "<codigo>"}` en los errores esperados.
- **Nueva página:** `<nombre>.html` + `js/pages/<nombre>.js`; empieza con `api.requireSession()` si es privada.
  No hay scripts ni estilos en línea: la CSP los bloquea.
- **Nuevo código de error:** añade su texto en `js/shared/api.js` y su fila en `docs/API.md`.

## Antes de publicar el repositorio
Mantenlo **privado**. Comprueba que no se versiona `.env` ni `certs/*.pem` (el `.gitignore` ya los excluye) y que ningún secreto
quedó en el historial de git.
