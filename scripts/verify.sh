#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python -m pytest --cov=marketlens --cov-report=term-missing
ruff check src tests app scripts
ruff format --check src tests app scripts
