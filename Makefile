# ──────────────────────────────────────────────────
#  mythosaur-tools — MCP companion stack
# ──────────────────────────────────────────────────

.PHONY: help up down restart logs config test commit \
        google-login google-login-ssh notebooklm-login \
        _check-env

DEFAULT_GOAL := help

# ──────────────────────────────────────────────────
#  Variables
# ──────────────────────────────────────────────────

COMPOSE    := docker compose --env-file .env -f docker-compose.yml
UV         ?= uv
OAUTH_PORT ?= 8085

# ──────────────────────────────────────────────────
#  Help
# ──────────────────────────────────────────────────

help:
	@echo ""
	@echo "  mythosaur-tools — MCP companion stack"
	@echo "  ─────────────────────────────────────"
	@echo ""
	@echo "  Runtime:"
	@echo "    make up              Start the tools stack"
	@echo "    make down            Stop the tools stack"
	@echo "    make restart         Restart the tools stack"
	@echo "    make logs [S=name]   Tail logs"
	@echo "    make config          Render docker compose config"
	@echo ""
	@echo "  Auth:"
	@echo "    make google-login      Create or refresh Google OAuth and NotebookLM auth"
	@echo "    make google-login-ssh  Google OAuth via SSH (paste redirect URL manually)"
	@echo "    make notebooklm-login"
	@echo ""
	@echo "  Dev:"
	@echo "    make test            Run backend tests"
	@echo "    make commit          Stage all changes and commit interactively"
	@echo ""

# ──────────────────────────────────────────────────
#  Runtime (Docker Compose)
# ──────────────────────────────────────────────────

up: _check-env
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

restart: _check-env
	$(COMPOSE) restart

logs:
	@[ -z "$(S)" ] && $(COMPOSE) logs -f --tail 50 || \
		$(COMPOSE) logs -f --tail 50 $(S)

config: _check-env
	@$(COMPOSE) config

# ──────────────────────────────────────────────────
#  Testing
# ──────────────────────────────────────────────────

test:
	@$(UV) run --with-requirements services/mcp_server/requirements.txt python -m pytest tests/test_google_workspace_tools.py tests/test_app.py

# ──────────────────────────────────────────────────
#  Auth — Google OAuth & NotebookLM
# ──────────────────────────────────────────────────

google-login: _check-env
	@credentials_rel="$$(sed -n 's/^MYTHOSAUR_TOOLS_GOOGLE_CREDENTIALS_FILE=//p' .env 2>/dev/null | tail -n 1)"; \
	token_rel="$$(sed -n 's/^MYTHOSAUR_TOOLS_GOOGLE_TOKEN_FILE=//p' .env 2>/dev/null | tail -n 1)"; \
	preset="$${PRESET:-workspace}"; \
	credentials_rel="$${credentials_rel:-/secrets/google-credentials.json}"; \
	token_rel="$${token_rel:-/secrets/google-token.json}"; \
	case "$$credentials_rel" in \
		/secrets/*) credentials_path="$(CURDIR)/secrets/$${credentials_rel#/secrets/}" ;; \
		/data/*) credentials_path="$(CURDIR)/secrets/$${credentials_rel#/data/}" ;; \
		/*) credentials_path="$$credentials_rel" ;; \
		*) credentials_path="$(CURDIR)/$$credentials_rel" ;; \
	esac; \
	case "$$token_rel" in \
		/secrets/*) token_path="$(CURDIR)/secrets/$${token_rel#/secrets/}" ;; \
		/data/*) token_path="$(CURDIR)/secrets/$${token_rel#/data/}" ;; \
		/*) token_path="$$token_rel" ;; \
		*) token_path="$(CURDIR)/$$token_rel" ;; \
	esac; \
	if [ ! -f "$$credentials_path" ]; then \
		echo "Missing Google OAuth client file: $$credentials_path"; \
		echo "Place your Google Cloud OAuth credentials JSON there, then rerun \`make google-login\`."; \
		exit 1; \
	fi; \
	mkdir -p "$$(dirname "$$token_path")"; \
	echo "Running Google OAuth flow from $(CURDIR) ..."; \
	$(UV) run --with google-auth-oauthlib --with google-auth --with google-api-python-client \
		python scripts/google_oauth_bootstrap.py \
		--credentials "$$credentials_path" \
		--token "$$token_path" \
		--preset "$$preset"; \
	$(MAKE) --no-print-directory notebooklm-login

google-login-ssh: _check-env
	@credentials_rel="$$(sed -n 's/^MYTHOSAUR_TOOLS_GOOGLE_CREDENTIALS_FILE=//p' .env 2>/dev/null | tail -n 1)"; \
	token_rel="$$(sed -n 's/^MYTHOSAUR_TOOLS_GOOGLE_TOKEN_FILE=//p' .env 2>/dev/null | tail -n 1)"; \
	preset="$${PRESET:-workspace}"; \
	credentials_rel="$${credentials_rel:-/secrets/google-credentials.json}"; \
	token_rel="$${token_rel:-/secrets/google-token.json}"; \
	case "$$credentials_rel" in \
		/secrets/*) credentials_path="$(CURDIR)/secrets/$${credentials_rel#/secrets/}" ;; \
		/data/*) credentials_path="$(CURDIR)/secrets/$${credentials_rel#/data/}" ;; \
		/*) credentials_path="$$credentials_rel" ;; \
		*) credentials_path="$(CURDIR)/$$credentials_rel" ;; \
	esac; \
	case "$$token_rel" in \
		/secrets/*) token_path="$(CURDIR)/secrets/$${token_rel#/secrets/}" ;; \
		/data/*) token_path="$(CURDIR)/secrets/$${token_rel#/data/}" ;; \
		/*) token_path="$$token_rel" ;; \
		*) token_path="$(CURDIR)/$$token_rel" ;; \
	esac; \
	if [ ! -f "$$credentials_path" ]; then \
		echo "Missing Google OAuth client file: $$credentials_path"; \
		echo "Place your Google Cloud OAuth credentials JSON there, then rerun."; \
		exit 1; \
	fi; \
	mkdir -p "$$(dirname "$$token_path")"; \
	echo ""; \
	echo "  Google OAuth — SSH mode"; \
	echo "  ───────────────────────"; \
	echo ""; \
	$(UV) run --with google-auth-oauthlib --with google-auth --with google-api-python-client \
		python scripts/google_oauth_bootstrap.py \
		--credentials "$$credentials_path" \
		--token "$$token_path" \
		--preset "$$preset" \
		--force --no-browser --port $(OAUTH_PORT) & \
	bg_pid=$$!; \
	sleep 2; \
	echo ""; \
	echo "  Steps:"; \
	echo "    1. Open the URL above in any browser"; \
	echo "    2. Authorize the Google account"; \
	echo "    3. The browser will redirect to http://127.0.0.1:$(OAUTH_PORT)/?..."; \
	echo "       (the page won't load — that is expected)"; \
	echo "    4. Copy the FULL URL from the browser address bar"; \
	echo "    5. Paste it below and press Enter"; \
	echo ""; \
	printf "  Redirect URL: "; \
	read redirect_url </dev/tty; \
	echo ""; \
	echo "  Completing OAuth flow..."; \
	curl -s "$$redirect_url" > /dev/null 2>&1; \
	wait $$bg_pid 2>/dev/null; \
	echo "  Done. Token written to $$token_path"; \
	echo ""; \
	$(MAKE) --no-print-directory notebooklm-login

notebooklm-login: _check-env
	@notebooklm_enabled="$$(sed -n 's/^MYTHOSAUR_TOOLS_NOTEBOOKLM_ENABLED=//p' .env 2>/dev/null | tail -n 1)"; \
	notebooklm_profile="$$(sed -n 's/^MYTHOSAUR_TOOLS_NOTEBOOKLM_PROFILE=//p' .env 2>/dev/null | tail -n 1)"; \
	notebooklm_cli_rel="$$(sed -n 's/^NOTEBOOKLM_MCP_CLI_PATH=//p' .env 2>/dev/null | tail -n 1)"; \
	notebooklm_enabled="$${notebooklm_enabled:-true}"; \
	notebooklm_profile="$${notebooklm_profile:-default}"; \
	notebooklm_cli_rel="$${notebooklm_cli_rel:-/secrets/notebooklm}"; \
	case "$$notebooklm_cli_rel" in \
		/secrets/*) notebooklm_cli_path="$(CURDIR)/secrets/$${notebooklm_cli_rel#/secrets/}" ;; \
		/data/*) notebooklm_cli_path="$(CURDIR)/secrets/$${notebooklm_cli_rel#/data/}" ;; \
		/*) notebooklm_cli_path="$$notebooklm_cli_rel" ;; \
		*) notebooklm_cli_path="$(CURDIR)/$$notebooklm_cli_rel" ;; \
	esac; \
	case "$$(printf '%s' "$$notebooklm_enabled" | tr '[:upper:]' '[:lower:]')" in \
		1|true|yes|on) \
			mkdir -p "$$notebooklm_cli_path"; \
			echo "Running NotebookLM login for profile $$notebooklm_profile ..."; \
			NOTEBOOKLM_MCP_CLI_PATH="$$notebooklm_cli_path" \
				$(UV) tool run --from notebooklm-mcp-cli nlm login --profile "$$notebooklm_profile" \
			;; \
		*) \
			echo "Skipping NotebookLM login (MYTHOSAUR_TOOLS_NOTEBOOKLM_ENABLED=$$notebooklm_enabled)."; \
			;; \
	esac

# ──────────────────────────────────────────────────
#  Git helpers
# ──────────────────────────────────────────────────

commit:
	@echo "Adding all changes to git..."
	@git add .
	@bash -c 'read -p "Commit message: " MSG && git commit -m "$$MSG"'
	@echo "Commit created. Run 'git push' to push your changes."

# ──────────────────────────────────────────────────
#  Internal targets
# ──────────────────────────────────────────────────

_check-env:
	@[ -f .env ] || (echo "ERROR: .env not found. Run: cp .env.example .env" && exit 1)
