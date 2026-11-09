#!/usr/bin/env bash
# Build two publishable artefacts from the customer-simulators monorepo.
# Output layout matches what `next_release` expects (siblings of TARGET_DIR
# inside WORK_DIR):
#   - $WORK_DIR/customer-simulators-front/publish/  Vite-built static assets
#   - $WORK_DIR/customer-simulators-api/publish/    Django source tree +
#                                                   relocatable Python 3.12
#                                                   under .uv-python/ (with
#                                                   deps in .uv-python/deps/)
#                                                   + pre-collected static
#                                                   files + ./python wrapper.
#
# The API artefact is self-contained: no venv (which would record absolute
# paths), no system Python required on the deploy host. Just extract and
# run `./python manage.py runserver` from the package root.
#
# Build is hermetic: uv installs Python under the workdir
# (UV_PYTHON_INSTALL_DIR=$API_DIR/.uv-python), so nothing escapes the
# orchestrator's temp directory.
#
# Usage (standalone, from the repo root):
#   ./scripts/build_packages.sh [TARGET_DIR]
#
# TARGET_DIR defaults to the repo root, so the script can also be invoked
# in-place against the current working tree. Pass an explicit path when the
# orchestrator clones the repo elsewhere.
#
# Build-host requirements:
#   - bun on PATH (https://bun.sh/docs/installation)
#   - uv  on PATH (curl -LsSf https://astral.sh/uv/install.sh | sh)
#   - rsync
#
# Optional environment variables:
#   BUN_BIN                 bun executable     (default: bun on $PATH)
#   DJANGO_SETTINGS_MODULE  Django settings    (default: config.settings.prod)
#   VITE_API_URL,
#   VITE_VTF_BASE_URL       Baked into the Vite bundle at build time. Export
#                           in the orchestrator before calling this script.
#
# Frontend uses Bun (install + `bun run --bun build`) — sidesteps both the
# npm optional-deps bug around rolldown's native binding and Vite's strict
# Node-version check.
#
# -----------------------------------------------------------------------------
# Orchestrator integration — drop this block into the master build script,
# next to the other `if [[ "$r" == "..." ]]` blocks:
# -----------------------------------------------------------------------------
# ### CUSTOMER SIMULATORS (VTF) UPDATE
# if [[ "$r" == "Uptoone/customer-simulators" ]]
# then
# cd $WORK_DIR || error_exit "Failed to change directory to $WORK_DIR"
# TARGET_DIR=$WORK_DIR/customer-simulators
# GIT_SSH_COMMAND='ssh -i /root/.ssh/id_rsacustomersimulators -o IdentitiesOnly=yes' \
#     git clone -b ${b} --single-branch git@github.com:${r}.git
#     if [[ $? -ne 0 ]] ; then
#         echo "LAST VERSION FETCH NOT POSSIBLE  - stall updates"
#         exit 1
#     fi
#
# bash $TARGET_DIR/scripts/build_packages.sh $TARGET_DIR \
#     || error_exit "build_packages.sh failed"
#
# # The script stages each package at $WORK_DIR/<name>/publish/, which
# # is exactly where next_release looks for it.
# cd $WORK_DIR/customer-simulators-front/publish \
#     || error_exit "Failed to cd to front publish"
# next_release "customer-simulators-front"
#
# cd $WORK_DIR/customer-simulators-api/publish \
#     || error_exit "Failed to cd to api publish"
# next_release "customer-simulators-api"
# fi
# -----------------------------------------------------------------------------

set -euo pipefail

# Make user-local tool installs (uv, bun, etc. — anything dropped under
# ~/.local/bin by curl install scripts) reachable from non-interactive
# shells whose PATH skips that directory by default.
export PATH="${HOME:-/root}/.local/bin:$PATH"

TARGET_DIR="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
WORK_DIR="$(dirname "$TARGET_DIR")"
FRONT_DIR="$TARGET_DIR/vtf/front"
API_DIR="$TARGET_DIR/vtf/api"

# next_release looks up $WORK_DIR/<package-name>/publish, so stage each
# artefact at the location it expects rather than under $TARGET_DIR/publish.
FRONT_PUBLISH="$WORK_DIR/customer-simulators-front/publish"
API_PUBLISH="$WORK_DIR/customer-simulators-api/publish"

echo "[build_packages] TARGET_DIR=$TARGET_DIR"
echo "[build_packages] WORK_DIR=$WORK_DIR"

[[ -d "$FRONT_DIR" ]] || { echo "[build_packages] missing $FRONT_DIR"; exit 1; }
[[ -d "$API_DIR"   ]] || { echo "[build_packages] missing $API_DIR";   exit 1; }

rm -rf "$FRONT_PUBLISH" "$API_PUBLISH"
mkdir -p "$FRONT_PUBLISH" "$API_PUBLISH"

# -----------------------------------------------------------------------------
# Frontend — React + Vite + TypeScript
# -----------------------------------------------------------------------------
echo "[build_packages] === FRONTEND ==="
cd "$FRONT_DIR"

BUN_BIN="${BUN_BIN:-bun}"
"$BUN_BIN" install
"$BUN_BIN" run --bun build

cp -a "$FRONT_DIR/dist/." "$FRONT_PUBLISH/"
echo "[build_packages] front staged at $FRONT_PUBLISH"

# -----------------------------------------------------------------------------
# Backend — Django + DRF
# -----------------------------------------------------------------------------
echo "[build_packages] === BACKEND ==="
cd "$API_DIR"

if ! command -v uv >/dev/null 2>&1; then
  echo "[build_packages] uv not on PATH (looked in \$PATH and ${HOME:-/root}/.local/bin)." >&2
  echo "[build_packages] Install: curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
  echo "[build_packages] Or symlink an existing uv into /usr/local/bin to make it system-wide." >&2
  exit 1
fi

# Pin uv's Python install to the API dir so the interpreter ships with the
# package. python-build-standalone (what uv installs) is fully relocatable,
# so .uv-python/ works at any path on a compatible Linux host.
export UV_PYTHON_INSTALL_DIR="$API_DIR/.uv-python"
uv python install 3.12
PYTHON_BIN="$(uv python find 3.12)"
echo "[build_packages] uv-managed python at $PYTHON_BIN"

# Install deps to .uv-python/deps/ via --target instead of a venv. A venv
# records absolute paths (pyvenv.cfg `home`, symlinks in bin/) that break
# when the package moves from build host to deploy host. --target keeps
# everything inside the relocatable .uv-python tree.
DEPS_DIR="$API_DIR/.uv-python/deps"
rm -rf "$DEPS_DIR"
mkdir -p "$DEPS_DIR"
uv pip install --python "$PYTHON_BIN" --target "$DEPS_DIR" --quiet \
    -r "$API_DIR/requirements.txt"

# Pre-collect static so the deploy host can serve assets without running
# Django management commands. Prod settings require DJANGO_SECRET_KEY at
# import time (see config/settings/prod.py) — a throwaway value is fine
# here; the real key is set on the deploy host.
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings.prod}"
export DJANGO_SECRET_KEY="${DJANGO_SECRET_KEY:-build-time-throwaway-$(date +%s)}"
PYTHONPATH="$DEPS_DIR" "$PYTHON_BIN" "$API_DIR/manage.py" collectstatic --noinput

# Stage the source tree (including .uv-python with bundled interpreter and
# deps). Exclude .data/ wholesale, then copy .data/staticfiles back in —
# keeps both rsync filters and intent simple.
rsync -a \
    --exclude='.venv/' \
    --exclude='.data/' \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    --exclude='.env' \
    --exclude='.env.*' \
    --exclude='docs/' \
    --exclude='tests/' \
    --exclude='publish/' \
    --exclude='.gitignore' \
    --exclude='.dockerignore' \
    "$API_DIR/" "$API_PUBLISH/"

if [[ -d "$API_DIR/.data/staticfiles" ]]; then
    mkdir -p "$API_PUBLISH/.data"
    cp -a "$API_DIR/.data/staticfiles" "$API_PUBLISH/.data/"
fi

# Convenience wrapper: sets PYTHONPATH and execs the bundled interpreter.
# Deploy host runs `./python manage.py runserver`, no venv activation, no
# need to know the cpython-3.12-… directory name.
cat > "$API_PUBLISH/python" <<'PYWRAPPER_EOF'
#!/usr/bin/env bash
HERE="$(cd "$(dirname "$0")" && pwd)"
for p in "$HERE"/.uv-python/cpython-*/bin/python3.12; do
    PYTHONPATH="$HERE/.uv-python/deps${PYTHONPATH:+:$PYTHONPATH}" \
        exec "$p" "$@"
done
echo "[python] no interpreter under $HERE/.uv-python/" >&2
exit 1
PYWRAPPER_EOF
chmod +x "$API_PUBLISH/python"

echo "[build_packages] api staged at $API_PUBLISH"
echo "[build_packages] done."
