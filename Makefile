# Money You're Missing - developer commands.
#
# Every target delegates to scripts/tasks.py, which holds the real
# implementation. That is deliberate: `make` is not available on a default
# Windows install, and a Makefile plus a parallel batch file reliably drift
# apart. One implementation, two front doors:
#
#     make setup                       (macOS, Linux, CI)
#     python scripts/tasks.py setup    (everywhere, including Windows)
#
# Everything works on a fresh clone with no credentials: `make setup && make
# dev` gives a running product with demo and curated opportunities,
# deterministic matching, the Germany check and the German knowledge corpus.
# Adding API keys turns on CV extraction, live search and written explanations.

PYTHON ?= python
RUN := $(PYTHON) scripts/tasks.py

.DEFAULT_GOAL := help
.PHONY: help setup setup-backend setup-frontend data migrate seed \
        dev dev-api dev-web test test-backend test-frontend e2e eval \
        lint format typecheck check build docker-build clean reset

help: ## Show the available tasks
	@$(RUN) --help

setup:          ## Install everything and prepare the database (start here)
	@$(RUN) setup
setup-backend:  ## Install backend dependencies from the lockfile
	@$(RUN) setup-backend
setup-frontend: ## Install frontend dependencies from the lockfile
	@$(RUN) setup-frontend

data:    ## Regenerate the knowledge corpus and opportunity datasets
	@$(RUN) data
migrate: ## Apply database migrations
	@$(RUN) migrate
seed:    ## Load legal facts, ingest the corpus, register sources (idempotent)
	@$(RUN) seed

dev:     ## Run the API and the web app together
	@$(RUN) dev
dev-api: ## Run the API only, on :8000
	@$(RUN) dev-api
dev-web: ## Run the web app only, on :3000
	@$(RUN) dev-web

test:          ## All unit tests
	@$(RUN) test
test-backend:  ## Backend tests (no network, no paid model calls)
	@$(RUN) test-backend
test-frontend: ## Frontend unit tests
	@$(RUN) test-frontend
e2e:           ## End-to-end tests (needs the API on :8000)
	@$(RUN) e2e
eval:          ## AI evaluation suite (scripted provider; costs nothing)
	@$(RUN) eval

lint:      ## Lint
	@$(RUN) lint
format:    ## Auto-fix what can be auto-fixed
	@$(RUN) format
typecheck: ## Type-check both halves
	@$(RUN) typecheck
check:     ## Everything CI runs
	@$(RUN) check

build:        ## Production build of the web app
	@$(RUN) build
docker-build: ## Build both container images
	@$(RUN) docker-build

clean: ## Remove build artefacts and caches
	@$(RUN) clean
reset: ## Delete the local database and rebuild it
	@$(RUN) reset
