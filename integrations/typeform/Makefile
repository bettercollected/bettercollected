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
build: ## Build integrations-typeform package
	echo "[build] Build integrations-typeform package."
	${POETRY_BINARY} build

.PHONY: install
install:  ## Install integrations-typeform with poetry
	@build/install.sh

.PHONY: image
image:  ## Build integrations-typeform image
	@build/image.sh

.PHONY: metrics
metrics: install ## Run integrations-typeform metrics checks
	echo "[metrics] Run integrations-typeform PEP 8 checks."
	${POETRY_BINARY} run flake8 --select=E,W,I --max-line-length 80 --import-order-style pep8 --statistics --count integrations_typeform
	echo "[metrics] Run integrations-typeform PEP 257 checks."
	${POETRY_BINARY} run flake8 --select=D --ignore D301 --statistics --count integrations_typeform
	echo "[metrics] Run integrations-typeform pyflakes checks."
	${POETRY_BINARY} run flake8 --select=F --statistics --count integrations_typeform
	echo "[metrics] Run integrations-typeform code complexity checks."
	${POETRY_BINARY} run flake8 --select=C901 --statistics --count integrations_typeform
	echo "[metrics] Run integrations-typeform open TODO checks."
	${POETRY_BINARY} run flake8 --select=T --statistics --count integrations_typeform tests
	echo "[metrics] Run integrations-typeform black checks."
	${POETRY_BINARY} run black -l 80 --check integrations_typeform

.PHONY: unit-test
unit-test: install ## Run integrations-typeform unit tests
	echo "[unit-test] Run integrations-typeform unit tests."
	${POETRY_BINARY} run pytest tests/unit

.PHONY: integration-test
integration-test: install ## Run integrations-typeform integration tests
	echo "[unit-test] Run integrations-typeform integration tests."
	${POETRY_BINARY} run pytest tests/integration

.PHONY: coverage
coverage: install  ## Run integrations-typeform tests coverage
	echo "[coverage] Run integrations-typeform tests coverage."
	${POETRY_BINARY} run pytest --cov=integrations_typeform --cov-fail-under=90 --cov-report=xml --cov-report=term-missing tests

.PHONY: test
test: unit-test integration-test  ## Run integrations-typeform tests

.PHONY: docs
docs: install ## Build integrations-typeform documentation
	echo "[docs] Build integrations-typeform documentation."
	${POETRY_BINARY} run sphinx-build docs site
