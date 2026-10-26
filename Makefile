# Makefile for testing the module.

SHELL = /bin/bash
PYTHON ?= python3
VENV ?= venv-${PYTHON}

IN_VENV = source "${VENV}/bin/activate" &&

.PHONY: setup artifacts tests coverage

setup: ${VENV}/marker

artifacts:
	mkdir -p artifacts

${VENV}/marker:
	-rm -rf "${VENV}"
	virtualenv -p "${PYTHON}" "${VENV}"
	source "${VENV}/bin/activate" && pip install -r requirements-test.txt
	touch "${VENV}/marker"

tests: setup artifacts
	${IN_VENV} ${PYTHON} -m pytest -v test_fontcontrols.py --junitxml artifacts/test-${PYTHON}.xml

coverage: setup artifacts
	-rm -rf .coverage
	${IN_VENV} ${PYTHON} -m pytest -v test_fontcontrols.py --cov control --cov-report term --cov-report html:artifacts/coverage-report --cov-report xml:artifacts/coverage.xml
