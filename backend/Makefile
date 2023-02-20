.DEFAULT_GOAL:=help

.EXPORT_ALL_VARIABLES:

ifndef VERBOSE
.SILENT:
endif

# set default shell
SHELL=/usr/bin/env bash -o pipefail -o errexit

TAG ?= $(shell cat TAG)
POETRY_HOME ?= ${HOME}/.local/share/pypoetry
POETRY_BINARY ?= ${POETRY_HOME}/venv/bin/poetry
POETRY_VERSION ?= 1.3.2

help:  ## Display this help
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z0-9_-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

.PHONY: show-version
show-version:  ## Display version
	echo -n "${TAG}"

.PHONY: build
build: ## Build backend package
	echo "[build] Build backend package."
	${POETRY_BINARY} build

.PHONY: install
install:  ## Install backend with poetry
	@build/install.sh

.PHONY: image
image:  ## Build backend image
	@build/image.sh

.PHONY: metrics
metrics: install ## Run backend metrics checks
	echo "[metrics] Run backend PEP 8 checks."
	${POETRY_BINARY} run flake8 --select=E,W,I --max-line-length 88 --import-order-style pep8 --statistics --count backend
	echo "[metrics] Run backend PEP 257 checks."
	${POETRY_BINARY} run flake8 --select=D --ignore D301 --statistics --count backend
	echo "[metrics] Run backend pyflakes checks."
	${POETRY_BINARY} run flake8 --select=F --statistics --count backend
	echo "[metrics] Run backend code complexity checks."
	${POETRY_BINARY} run flake8 --select=C901 --statistics --count backend
	echo "[metrics] Run backend open TODO checks."
	${POETRY_BINARY} run flake8 --select=T --statistics --count backend tests
	echo "[metrics] Run backend black checks."
	${POETRY_BINARY} run black -l 88 --check backend

.PHONY: unit-test
unit-test: install ## Run backend unit tests
	echo "[unit-test] Run backend unit tests."
	${POETRY_BINARY} run pytest tests/unit

.PHONY: integration-test
integration-test: install ## Run backend integration tests
	echo "[unit-test] Run backend integration tests."
	${POETRY_BINARY} run pytest tests/integration

.PHONY: coverage
coverage: install  ## Run backend tests coverage
	echo "[coverage] Run backend tests coverage."
	${POETRY_BINARY} run pytest --cov=backend --cov-fail-under=90 --cov-report=xml --cov-report=term-missing tests

.PHONY: test
test: unit-test integration-test  ## Run backend tests

.PHONY: format
format: install  ## Formats the python files with black
	echo "[format] Formatting the files."
	${POETRY_BINARY} run black . --exclude=venv --extend-exclude=common

.PHONY: flake8
flake8: install  ## Checks code standards with flake8
	echo "[flake8] Checking code standards with flake8."
	${POETRY_BINARY} run flake8 . --exclude=venv,common,.github,build,charts,manifests,site --extend-exclude=common

.PHONY: docs
docs: install ## Build backend documentation
	echo "[docs] Build backend documentation."
	${POETRY_BINARY} run sphinx-build docs site

.PHONY: dev-env
dev-env: image ## Start a local Kubernetes cluster using minikube and deploy application
	@build/dev-env.sh

.PHONY: clean
clean: ## Remove .cache directory and cached minikube
	minikube delete && rm -rf ~/.cache ~/.minikube
