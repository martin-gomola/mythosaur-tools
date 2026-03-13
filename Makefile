# ──────────────────────────────────────────────────
#  mythosaur-tools — MCP companion stack
# ──────────────────────────────────────────────────

.PHONY: help up down restart logs config test commit \
        codex-up codex-install codex-smoke \
        init-execution-bundle update-execution-bundle \
        google-login google-login-ssh notebooklm-login \
        notebooklm-login-manual _check-env

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
	@echo "    make codex-up        Start an IDE-facing stack with default consumer=codex"
	@echo ""
	@echo "  Auth:"
	@echo "    make google-login            Create or refresh Google OAuth and NotebookLM auth"
	@echo "    make google-login-ssh        Google OAuth via SSH (paste redirect URL manually)"
	@echo "    make notebooklm-login        NotebookLM login (launches Chrome)"
	@echo "    make notebooklm-login-manual NotebookLM login via cookies file (SSH-safe)"
	@echo ""
	@echo "  Dev:"
	@echo "    make test            Run backend tests"
	@echo "    make init-execution-bundle TITLE=... SUMMARY=... [SCOPE=plugin]"
	@echo "    make update-execution-bundle STATUS=..."
	@echo "    make codex-install   Export shared + Codex adapter skills"
	@echo "    make codex-smoke     Verify the Codex consumer catalog"
	@echo "    make commit          Stage all changes and commit interactively"
	@echo ""

# ──────────────────────────────────────────────────
#  Runtime (Docker Compose)
# ──────────────────────────────────────────────────

up: _check-env
	$(COMPOSE) up -d --build

codex-up: _check-env
	MT_DEFAULT_CONSUMER=codex $(COMPOSE) up -d --build

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

init-execution-bundle:
	@if [ -z "$(TITLE)" ] || [ -z "$(SUMMARY)" ]; then \
		echo "Usage: make init-execution-bundle TITLE='...' SUMMARY='...' [SCOPE=plugin]"; \
		exit 1; \
	fi
	@$(UV) run python scripts/init_execution_bundle.py --title "$(TITLE)" --summary "$(SUMMARY)" --scope "$(or $(SCOPE),plugin)"

update-execution-bundle:
	@if [ -z "$(STATUS)" ]; then \
		echo "Usage: make update-execution-bundle STATUS='completed|blocked|failed|in_progress|pending'"; \
		exit 1; \
	fi
	@$(UV) run python scripts/update_execution_bundle.py --status "$(STATUS)"

codex-install:
	@bash ./scripts/export-skills.sh --consumer codex

codex-smoke:
	@bash ./scripts/smoke_consumer_catalog.sh codex query
	@bash ./scripts/smoke_consumer_catalog.sh codex header

# ──────────────────────────────────────────────────
#  Auth — Google OAuth & NotebookLM
# ──────────────────────────────────────────────────

google-login: _check-env
	@credentials_rel="$$(sed -n -e 's/^MT_GOOGLE_CREDENTIALS_FILE=//p' -e 's/^MYTHOSAUR_TOOLS_GOOGLE_CREDENTIALS_FILE=//p' .env 2>/dev/null | tail -n 1)"; \
	token_rel="$$(sed -n -e 's/^MT_GOOGLE_TOKEN_FILE=//p' -e 's/^MYTHOSAUR_TOOLS_GOOGLE_TOKEN_FILE=//p' .env 2>/dev/null | tail -n 1)"; \
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
	@credentials_rel="$$(sed -n -e 's/^MT_GOOGLE_CREDENTIALS_FILE=//p' -e 's/^MYTHOSAUR_TOOLS_GOOGLE_CREDENTIALS_FILE=//p' .env 2>/dev/null | tail -n 1)"; \
	token_rel="$$(sed -n -e 's/^MT_GOOGLE_TOKEN_FILE=//p' -e 's/^MYTHOSAUR_TOOLS_GOOGLE_TOKEN_FILE=//p' .env 2>/dev/null | tail -n 1)"; \
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
	notebooklm_enabled="$$(sed -n -e 's/^MT_NOTEBOOKLM_ENABLED=//p' -e 's/^MYTHOSAUR_TOOLS_NOTEBOOKLM_ENABLED=//p' .env 2>/dev/null | tail -n 1)"; \
	notebooklm_enabled="$${notebooklm_enabled:-true}"; \
	case "$$(printf '%s' "$$notebooklm_enabled" | tr '[:upper:]' '[:lower:]')" in \
		1|true|yes|on) \
			echo "  NotebookLM login skipped (requires a browser)."; \
			echo "  To complete NotebookLM auth, choose one of:"; \
			echo "    • On a machine with a browser:  make notebooklm-login"; \
			echo "    • With an exported cookies file: make notebooklm-login-manual COOKIES=path/to/cookies.txt"; \
			echo ""; \
			;; \
		*) ;; \
	esac

notebooklm-login: _check-env
	@notebooklm_enabled="$$(sed -n -e 's/^MT_NOTEBOOKLM_ENABLED=//p' -e 's/^MYTHOSAUR_TOOLS_NOTEBOOKLM_ENABLED=//p' .env 2>/dev/null | tail -n 1)"; \
	notebooklm_profile="$$(sed -n -e 's/^MT_NOTEBOOKLM_PROFILE=//p' -e 's/^MYTHOSAUR_TOOLS_NOTEBOOKLM_PROFILE=//p' .env 2>/dev/null | tail -n 1)"; \
	notebooklm_cli_rel="$$(sed -n -e 's/^MT_NOTEBOOKLM_MCP_CLI_PATH=//p' -e 's/^NOTEBOOKLM_MCP_CLI_PATH=//p' .env 2>/dev/null | tail -n 1)"; \
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
			echo "Skipping NotebookLM login (MT_NOTEBOOKLM_ENABLED=$$notebooklm_enabled)."; \
			;; \
	esac

notebooklm-login-manual: _check-env
	@notebooklm_enabled="$$(sed -n -e 's/^MT_NOTEBOOKLM_ENABLED=//p' -e 's/^MYTHOSAUR_TOOLS_NOTEBOOKLM_ENABLED=//p' .env 2>/dev/null | tail -n 1)"; \
	notebooklm_profile="$$(sed -n -e 's/^MT_NOTEBOOKLM_PROFILE=//p' -e 's/^MYTHOSAUR_TOOLS_NOTEBOOKLM_PROFILE=//p' .env 2>/dev/null | tail -n 1)"; \
	notebooklm_cli_rel="$$(sed -n -e 's/^MT_NOTEBOOKLM_MCP_CLI_PATH=//p' -e 's/^NOTEBOOKLM_MCP_CLI_PATH=//p' .env 2>/dev/null | tail -n 1)"; \
	notebooklm_enabled="$${notebooklm_enabled:-true}"; \
	notebooklm_profile="$${notebooklm_profile:-default}"; \
	notebooklm_cli_rel="$${notebooklm_cli_rel:-/secrets/notebooklm}"; \
	case "$$notebooklm_cli_rel" in \
		/secrets/*) notebooklm_cli_path="$(CURDIR)/secrets/$${notebooklm_cli_rel#/secrets/}" ;; \
		/data/*) notebooklm_cli_path="$(CURDIR)/secrets/$${notebooklm_cli_rel#/data/}" ;; \
		/*) notebooklm_cli_path="$$notebooklm_cli_rel" ;; \
		*) notebooklm_cli_path="$(CURDIR)/$$notebooklm_cli_rel" ;; \
	esac; \
	cookies_path="$(COOKIES)"; \
	case "$$(printf '%s' "$$notebooklm_enabled" | tr '[:upper:]' '[:lower:]')" in \
		1|true|yes|on) \
			if [ -z "$$cookies_path" ]; then \
				echo ""; \
				echo "  NotebookLM manual login — SSH-safe (no browser needed)"; \
				echo "  ─────────────────────────────────────────────────────"; \
				echo ""; \
				echo "  Usage: make notebooklm-login-manual COOKIES=path/to/cookies.txt"; \
				echo ""; \
				echo "  To get the cookies file:"; \
				echo "    1. Open https://notebooklm.google.com in a browser"; \
				echo "    2. Sign in with the target Google account"; \
				echo "    3. Export cookies (use a browser extension or DevTools)"; \
				echo "    4. Save them to a file and pass the path via COOKIES="; \
				echo ""; \
				exit 1; \
			fi; \
			if [ ! -f "$$cookies_path" ]; then \
				echo "Cookie file not found: $$cookies_path"; \
				exit 1; \
			fi; \
			mkdir -p "$$notebooklm_cli_path"; \
			echo "Running NotebookLM manual login for profile $$notebooklm_profile ..."; \
			NOTEBOOKLM_MCP_CLI_PATH="$$notebooklm_cli_path" \
				$(UV) tool run --from notebooklm-mcp-cli nlm login \
				--manual --file "$$cookies_path" --profile "$$notebooklm_profile" \
			;; \
		*) \
			echo "Skipping NotebookLM login (MT_NOTEBOOKLM_ENABLED=$$notebooklm_enabled)."; \
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
