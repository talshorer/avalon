#! /bin/bash

PYTHON=${PYTHON-python}

$PYTHON -m mypy --strict .
$PYTHON -m isort .
$PYTHON -m black .
