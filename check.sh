#! /bin/bash

set -e

PYTHON=${PYTHON-python3}

$PYTHON -m isort .
$PYTHON -m black .
$PYTHON -m pyflakes *.py
$PYTHON -m pytest -v .
$PYTHON -m mypy --strict .
