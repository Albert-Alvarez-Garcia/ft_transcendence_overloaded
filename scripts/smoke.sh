#!/usr/bin/env bash
# Prueba de humo: make smoke
# Opcional, para probar tambien la parte con sesion (usuario ya verificado):
#   SMOKE_USER=nombre SMOKE_PASS=clave make smoke
BASE="${BASE:-https://localhost:8443}"
JAR="$(mktemp)"; trap 'rm -f "$JAR"' EXIT
fail=0

req()  { curl -ks -b "$JAR" -c "$JAR" -H 'Content-Type: application/json' "$@"; }
code() { curl -ks -o /dev/null -w '%{http_code}' "$@"; }
check() {  # nombre, salida, patron esperado
  if printf '%s' "$2" | grep -q "$3"; then echo "OK     $1"; else echo "FALLO  $1  ->  $2"; fail=1; fi
}

check "health"                    "$(req "$BASE/api/health")" '"ok":true'
check "me sin sesion"             "$(req "$BASE/api/auth/me")" '"authenticated":false'
check "login erroneo (HTTP 200)"  "$(req -X POST "$BASE/api/auth/login" -d '{"identifier":"nadie","password":"mala-clave"}')" 'invalid_credentials'
check "registro invalido"         "$(req -X POST "$BASE/api/auth/register" -d '{"username":"x","email":"a@b.co","password":"12345678"}')" 'invalid_username'
check "test sin sesion"           "$(req "$BASE/api/test")" 'unauthenticated'
check "pagina de login (200)"     "$(code "$BASE/login.html")" '^200$'
check "URL inexistente (404)"     "$(code "$BASE/no-existe.html")" '^404$'
check "HTTP redirige a HTTPS"     "$(code http://localhost:8080/login.html)" '^301$'

if [ -n "$SMOKE_USER" ] && [ -n "$SMOKE_PASS" ]; then
  check "login correcto"          "$(req -X POST "$BASE/api/auth/login" -d "{\"identifier\":\"$SMOKE_USER\",\"password\":\"$SMOKE_PASS\"}")" '"ok":true'
  check "me con sesion"           "$(req "$BASE/api/auth/me")" '"authenticated":true'
  req -X DELETE "$BASE/api/test" >/dev/null
  check "test: crear"             "$(req -X POST "$BASE/api/test")" '"value":true'
  check "test: crear otra vez"    "$(req -X POST "$BASE/api/test")" 'already_exists'
  check "test: modificar"         "$(req -X PUT "$BASE/api/test")" '"value":false'
  check "test: consultar"         "$(req "$BASE/api/test")" '"value":false'
  check "test: borrar"            "$(req -X DELETE "$BASE/api/test")" '"value":null'
  check "logout"                  "$(req -X POST "$BASE/api/auth/logout" -d '{}')" '"ok":true'
  check "me tras logout"          "$(req "$BASE/api/auth/me")" '"authenticated":false'
else
  echo "(sin SMOKE_USER/SMOKE_PASS: se omiten las pruebas con sesion)"
fi

[ "$fail" -eq 0 ] && echo "Todo correcto" || { echo "Hay fallos"; exit 1; }
