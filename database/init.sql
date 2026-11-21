CREATE TABLE users (
    id              SERIAL PRIMARY KEY,
    username        VARCHAR(20)  NOT NULL,
    email           VARCHAR(254) NOT NULL UNIQUE,
    password_hash   TEXT,                       -- NULL si solo entra con 42
    email_verified  BOOLEAN NOT NULL DEFAULT FALSE,
    verify_token_hash TEXT,
    verify_expires  TIMESTAMPTZ,
    fortytwo_id     INTEGER UNIQUE,
    test            BOOLEAN,                    -- campo de la pagina "test api": NULL / true / false
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX users_username_lower ON users (lower(username));

CREATE TABLE sessions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    method      VARCHAR(10) NOT NULL,           -- 'password' | '42'
    ip          TEXT,
    user_agent  TEXT,
    login_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    logout_at   TIMESTAMPTZ                     -- NULL = abierta (o caducada sin cerrar)
);
CREATE INDEX sessions_user ON sessions (user_id, login_at DESC);
