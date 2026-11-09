# vtf/api — Django + DRF on Alpine
#
# Alpine baseline keeps the image small. We install C build deps so common
# Python packages with native extensions (psycopg, surprise, scipy if used)
# can compile cleanly. If you switch to wheels-only, drop `build-base`.

FROM python:3.12-alpine

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=0

# System deps:
#   - build-base        → gcc, make for native extensions
#   - musl-dev          → headers
#   - libffi-dev        → cryptography, cffi
#   - postgresql-dev    → psycopg (Phase 2+ when we move off SQLite)
#   - linux-headers     → some scientific libs
#   - bash, curl, git   → quality of life in dev
RUN apk add --no-cache \
      build-base musl-dev libffi-dev postgresql-dev linux-headers \
      bash curl git

WORKDIR /app

# Install requirements ahead of code so the layer is cached when only
# source files change. The `requirements.txt` is created during Milestone 0
# (see vtf/api/docs/09-implementation-roadmap.md). We only install if it
# already exists, otherwise we let the container start "empty" so the dev
# can bootstrap from inside.
COPY requirements.txt* ./
RUN if [ -f requirements.txt ]; then \
      pip install -r requirements.txt; \
    else \
      echo "[vtf-api build] no requirements.txt yet — skipping pip install"; \
    fi

EXPOSE 8000

# docker-compose overrides this with the runserver/sleep loop.
CMD ["python", "-c", "print('Bootstrap the Django project first — see docs/09-implementation-roadmap.md')"]
