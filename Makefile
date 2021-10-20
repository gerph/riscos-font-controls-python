# Makefile for testing the module.

SHELL = /bin/bash
PYTHON ?= python2
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
	${IN_VENV} ${PYTHON} test_fontcontrols.py -v --xunit-file artifacts/test-${PYTHON}.xml

coverage: setup
	-rm -rf .coverage
	${IN_VENV} ${PYTHON} test_fontcontrols.py -v --with-coverage --cover-html --cover-package control
