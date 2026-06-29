#!/usr/bin/env bash
set -euo pipefail

.venv/bin/python -m pytest -q
.venv/bin/ruff check .
git diff --check

