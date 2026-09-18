#!/usr/bin/env bash
# Полный конвейер ЦКС → кримпаспорт (из корня репозитория)
set -euo pipefail
cd "$(dirname "$0")/../.."
PY="${PY:-.venv/bin/python}"
"$PY" scripts/cks/verify_sources.py
"$PY" scripts/cks/normalize_persons.py
"$PY" scripts/cks/crossmatch_cks.py
"$PY" scripts/cks/build_cks_data.py
"$PY" scripts/build_cks_dashboard.py
"$PY" passports/scripts/build.py
"$PY" scripts/cks/final_check.py
echo "Готово: docs/cks.html, private/cks_operativ.html"
