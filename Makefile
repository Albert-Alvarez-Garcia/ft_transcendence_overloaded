COMPOSE = docker compose
DEV = $(COMPOSE) -f docker-compose.yml -f docker-compose.dev.yml
.PHONY: help certs preflight up dev down restart logs status sessions smoke clean re

help: ## Muestra esta ayuda
	@grep -E '^[a-z]+:.*##' $(MAKEFILE_LIST) | sed 's/:.*## /\t/'

certs: ## Genera el certificado autofirmado si no existe
	@mkdir -p certs
	@test -f certs/cert.pem -a -f certs/key.pem || openssl req -x509 -newkey rsa:2048 -nodes -days 365 -keyout certs/key.pem -out certs/cert.pem -subj "/CN=localhost" -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"

preflight:
	@test -f .env || (echo "Falta .env: copia el tuyo aqui (ver .env.example)"; exit 1)

up: preflight certs ## ENTREGA: construye y arranca todo
	$(COMPOSE) up -d --build --remove-orphans
	@echo "Listo: https://localhost:8443"

dev: preflight certs ## DESARROLLO: recarga automatica + correo falso (Mailpit)
	$(DEV) up -d --build
	@echo "Listo: https://localhost:8443  |  correos: http://localhost:8025"

down: ## Para los contenedores (en cualquier modo)
	$(DEV) down --remove-orphans

restart: down up ## Reinicia en modo entrega

logs: ## Logs en directo
	$(DEV) logs -f

status: ## Estado de los contenedores
	$(DEV) ps

sessions: ## Ultimas 20 sesiones registradas
	$(DEV) exec -T postgres_db sh -c 'psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB" -c "SELECT u.username, s.method, s.ip, s.login_at, s.logout_at, left(s.user_agent,40) AS navegador FROM sessions s JOIN users u ON u.id=s.user_id ORDER BY s.login_at DESC LIMIT 20;"'

smoke: ## Prueba de humo contra https://localhost:8443
	@bash scripts/smoke.sh

clean: ## Para y BORRA los datos (volumen de la base de datos)
	$(DEV) down -v --remove-orphans

re: clean up ## Borra todo y arranca de cero (modo entrega)
