#!/bin/bash
# Claude Fleet launcher. Prefer uv; fall back to a local venv when uv is absent.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

load_env_file() {
    local env_file="$1"
    local line key value

    while IFS= read -r line || [ -n "$line" ]; do
        line="${line%$'\r'}"
        [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
        if [[ "$line" =~ ^[[:space:]]*export[[:space:]]+(.+)$ ]]; then
            line="${BASH_REMATCH[1]}"
        fi
        line="$(strip_inline_comment "$line")"
        line="$(trim_outer_space "$line")"
        [ -z "$line" ] && continue
        if [[ ! "$line" =~ ^[[:space:]]*([A-Za-z_][A-Za-z0-9_]*)=(.*)$ ]]; then
            echo "[claude-fleet] ignoring invalid .env.local line" >&2
            continue
        fi

        key="${BASH_REMATCH[1]}"
        value="${BASH_REMATCH[2]}"
        if [ "${#value}" -ge 2 ]; then
            if [[ "$value" == \"*\" && "$value" == *\" ]]; then
                value="${value:1:${#value}-2}"
            elif [[ "$value" == \'*\' && "$value" == *\' ]]; then
                value="${value:1:${#value}-2}"
            fi
        fi

        case "$key" in
            CLAUDE_FLEET_*|WATCHFILES_*)
                if [ -z "${!key+x}" ]; then
                    export "$key=$value"
                fi
                ;;
            *)
                echo "[claude-fleet] ignoring unsupported .env.local key: $key" >&2
                ;;
        esac
    done < "$env_file"
}

strip_inline_comment() {
    local input="$1"
    local out="" quote="" ch
    local i

    for (( i = 0; i < ${#input}; i++ )); do
        ch="${input:i:1}"
        if [ -n "$quote" ]; then
            out+="$ch"
            [ "$ch" = "$quote" ] && quote=""
            continue
        fi
        if [ "$ch" = "'" ] || [ "$ch" = '"' ]; then
            quote="$ch"
            out+="$ch"
            continue
        fi
        if [ "$ch" = "#" ] && [[ -z "$out" || "$out" =~ [[:space:]]$ ]]; then
            break
        fi
        out+="$ch"
    done
    printf "%s" "$out"
}

trim_outer_space() {
    local value="$1"
    value="${value#"${value%%[![:space:]]*}"}"
    value="${value%"${value##*[![:space:]]}"}"
    printf "%s" "$value"
}

valid_port() {
    local port="$1"
    [[ "$port" =~ ^[0-9]+$ ]] && (( 10#$port >= 1 && 10#$port <= 65535 ))
}

# Per-host overrides (gitignored). Use for machine-specific settings like
# CLAUDE_FLEET_CWD_INCLUDE without committing them. The file is parsed as
# literal KEY=value entries with shell-style comments and is not executed.
if [ -f .env.local ]; then
    load_env_file .env.local
fi

PORT="${CLAUDE_FLEET_PORT:-7879}"
if ! valid_port "$PORT"; then
    echo "[claude-fleet] invalid CLAUDE_FLEET_PORT: $PORT" >&2
    exit 1
fi
echo "[claude-fleet] listening on http://127.0.0.1:${PORT}"

# This repo often lives on a network/shared mount (e.g. /shared) where inotify
# events don't fire, so uvicorn's default --reload silently never detects edits
# and the server keeps serving stale code. Force watchfiles into polling mode and
# scope the watch to this dir so reload actually works here.
export WATCHFILES_FORCE_POLLING=1
RELOAD_ARGS=(--reload --reload-dir .)

setup_venv_runner() {
    RUNNER=()
    PYTHON_BIN=""
    for candidate in python3.12 python3.11 python3.10 python3; do
        if command -v "$candidate" >/dev/null 2>&1; then
            if "$candidate" -c 'import sys; raise SystemExit(sys.version_info < (3, 10))'; then
                PYTHON_BIN="$candidate"
                break
            fi
        fi
    done
    if [ -z "$PYTHON_BIN" ]; then
        echo "[claude-fleet] Python >=3.10 is required. Install uv or Python 3.10+." >&2
        exit 1
    fi
    if [ ! -d .venv ]; then
        echo "[claude-fleet] creating venv with ${PYTHON_BIN}..."
        "$PYTHON_BIN" -m venv .venv
    fi
    if [ ! -f .venv/bin/activate ]; then
        echo "[claude-fleet] invalid .venv; remove it or install uv." >&2
        exit 1
    fi
    source .venv/bin/activate
    if ! python -c 'import sys; raise SystemExit(sys.version_info < (3, 10))'; then
        echo "[claude-fleet] .venv uses Python <3.10; remove .venv or install uv." >&2
        exit 1
    fi
    if ! python -c "import fastapi, sse_starlette, uvicorn, watchfiles" 2>/dev/null; then
        echo "[claude-fleet] installing deps..."
        python -m pip install -q --upgrade pip setuptools wheel
        python -m pip install -q -e .
    fi
}

RUNNER=()
if command -v uv >/dev/null 2>&1; then
    if uv run --no-sync python -c 'import sys; raise SystemExit(sys.version_info < (3, 10))' >/dev/null 2>&1; then
        RUNNER=(uv run)
    else
        echo "[claude-fleet] uv is installed but unavailable; falling back to .venv." >&2
        setup_venv_runner
    fi
else
    setup_venv_runner
fi

UVICORN_CMD=(uvicorn app:app --host 127.0.0.1 --port "$PORT" "${RELOAD_ARGS[@]}")

start_detached() {
    local log_file="uvicorn.log"
    local launcher

    : > "$log_file"
    chmod 600 "$log_file" 2>/dev/null || true

    if command -v setsid >/dev/null 2>&1; then
        launcher="setsid"
        setsid "$@" >> "$log_file" 2>&1 < /dev/null &
    elif command -v nohup >/dev/null 2>&1; then
        launcher="nohup"
        nohup "$@" >> "$log_file" 2>&1 < /dev/null &
    else
        echo "[claude-fleet] neither setsid nor nohup is available; set CLAUDE_FLEET_FOREGROUND=1." >&2
        exit 1
    fi

    echo "[claude-fleet] started detached with ${launcher} (pid $!), logs -> ${log_file}"
}

run_foreground() {
    if [ "${#RUNNER[@]}" -gt 0 ]; then
        exec "${RUNNER[@]}" "${UVICORN_CMD[@]}"
    fi
    exec "${UVICORN_CMD[@]}"
}

run_detached() {
    if [ "${#RUNNER[@]}" -gt 0 ]; then
        start_detached "${RUNNER[@]}" "${UVICORN_CMD[@]}"
        return
    fi
    start_detached "${UVICORN_CMD[@]}"
}

# By default run detached so the server survives the launching shell/session.
# Set CLAUDE_FLEET_FOREGROUND=1 to run in the foreground instead.
if [ -n "${CLAUDE_FLEET_FOREGROUND:-}" ]; then
    run_foreground
fi

run_detached
