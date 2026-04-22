#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

DEFAULT_JULIA_BIN="/data/work/zhli/soft/julia-1.12.6/bin/julia"
JULIA_BIN="${DESIGN_MOTT_JULIA_BIN:-${DEFAULT_JULIA_BIN}}"

export JULIA_DEPOT_PATH="${DESIGN_MOTT_JULIA_DEPOT:-${PROJECT_ROOT}/scripts/.julia-depot}"
export JULIA_PKG_PRECOMPILE_AUTO="${JULIA_PKG_PRECOMPILE_AUTO:-0}"

exec "${JULIA_BIN}" \
  --project="${PROJECT_ROOT}/.julia-env-v09" \
  --startup-file=no \
  --history-file=no \
  --compiled-modules=no \
  --pkgimages=no \
  "$@"
