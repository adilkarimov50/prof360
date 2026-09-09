#!/bin/sh
set -e
cd /app
if [ "${SKIP_DB_INIT:-0}" != "1" ]; then
  alembic upgrade head 2>/dev/null || true
  if [ "${RUN_BOOTSTRAP:-0}" = "1" ]; then
    python manage.py all || true
    python manage.py tag-norms || true
    python manage.py link-norms || true
    python manage.py legal-index || true
  fi
fi
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
