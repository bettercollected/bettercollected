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
POETRY_VERSION ?= 1.2.0

help:  ## Display this help
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z0-9_-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

.PHONY: show-version
show-version:  ## Display version
	echo -n "${TAG}"

.PHONY: build
build: ## Build typeform package
	echo "[build] Build typeform package."
	${POETRY_BINARY} build

.PHONY: install
install:  ## Install typeform with poetry
	@build/install.sh

.PHONY: image
image:  ## Build typeform image
	@build/image.sh

.PHONY: metrics
metrics: install ## Run typeform metrics checks
	echo "[metrics] Run typeform PEP 8 checks."
	${POETRY_BINARY} run flake8 --select=E,W,I --max-line-length 80 --import-order-style pep8 --statistics --count typeform
	echo "[metrics] Run typeform PEP 257 checks."
	${POETRY_BINARY} run flake8 --select=D --ignore D301 --statistics --count typeform
	echo "[metrics] Run typeform pyflakes checks."
	${POETRY_BINARY} run flake8 --select=F --statistics --count typeform
	echo "[metrics] Run typeform code complexity checks."
	${POETRY_BINARY} run flake8 --select=C901 --statistics --count typeform
	echo "[metrics] Run typeform open TODO checks."
	${POETRY_BINARY} run flake8 --select=T --statistics --count typeform tests
	echo "[metrics] Run typeform black checks."
	${POETRY_BINARY} run black -l 80 --check typeform

.PHONY: unit-test
unit-test: install ## Run typeform unit tests
	echo "[unit-test] Run typeform unit tests."
	${POETRY_BINARY} run pytest tests/unit

.PHONY: integration-test
integration-test: install ## Run typeform integration tests
	echo "[unit-test] Run typeform integration tests."
	${POETRY_BINARY} run pytest tests/integration

.PHONY: coverage
coverage: install  ## Run typeform tests coverage
	echo "[coverage] Run typeform tests coverage."
	${POETRY_BINARY} run pytest --cov=typeform --cov-fail-under=60 --cov-report=xml --cov-report=term-missing tests

.PHONY: test
test: unit-test integration-test  ## Run typeform tests

.PHONY: format
format: install  ## Formats the python files with black
	echo "[format] Formatting the files."
	${POETRY_BINARY} run black . --exclude=venv --extend-exclude=common

.PHONY: flake8
flake8: install  ## Checks code standards with flake8
	echo "[flake8] Checking code standards with flake8."
	${POETRY_BINARY} run flake8 . --exclude=venv,common,.github,build,charts,manifests,site --extend-exclude=common

.PHONY: docs
docs: install ## Build typeform documentation
	echo "[docs] Build typeform documentation."
	${POETRY_BINARY} run sphinx-build docs site
