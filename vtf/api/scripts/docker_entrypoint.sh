#!/usr/bin/env bash
# Entrypoint for the `api` service in docker-compose.yml.
#
# Behaviour:
#   - Ensures the .data/ dir exists (SQLite + collected static).
#   - Runs `migrate` on every boot (idempotent).
#   - Loads fixtures only if the catalog is empty, so dev edits aren't wiped.
#     Disable with LOAD_FIXTURES_ON_BOOT=0.
#   - Default command is runserver on 0.0.0.0:8000; pass any other manage.py
#     subcommand as args (e.g. `docker compose run --rm api shell`).
set -euo pipefail

cd /app
mkdir -p .data

cmd="${1:-runserver}"
# Drop the dispatch arg so the catch-all branch can forward the rest verbatim
# to manage.py without duplicating it (e.g. `compose run api shell foo` would
# previously become `manage.py shell foo shell foo`).
shift || true

case "$cmd" in
  runserver)
    echo "[api] migrating..."
    python manage.py migrate --noinput

    if [ "${LOAD_FIXTURES_ON_BOOT:-1}" = "1" ]; then
      if python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
django.setup()
from apps.catalog.models import Village
import sys
sys.exit(0 if Village.objects.count() == 0 else 1)
" 2>/dev/null; then
        echo "[api] catalog empty -- loading fixtures..."
        python manage.py loaddata pricing_rules villages activities \
                                   meals fuel_options promos
      else
        echo "[api] catalog already seeded -- skipping loaddata."
      fi
    fi

    echo "[api] starting runserver on 0.0.0.0:8000"
    exec python manage.py runserver 0.0.0.0:8000
    ;;
  *)
    exec python manage.py "$cmd" "$@"
    ;;
esac
