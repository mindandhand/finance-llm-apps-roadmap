#!/usr/bin/env bash
set -euo pipefail

demo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
env_file="$demo_dir/.env"

if [[ ! -f "$env_file" ]]; then
    cp "$demo_dir/.env.example" "$env_file"
fi

set -a
source "$env_file"
set +a

: "${CUBE_SQL_PORT:=15432}"
: "${CUBE_SQL_USER:=cube}"
: "${CUBE_SQL_PASSWORD:=cube_sql_password}"
export CUBE_SQL_PORT CUBE_SQL_USER CUBE_SQL_PASSWORD

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    compose=(docker compose)
elif command -v podman >/dev/null 2>&1 && podman compose version >/dev/null 2>&1; then
    compose=(podman compose)
else
    echo "Docker Compose or Podman Compose is required." >&2
    exit 1
fi

run_compose() {
    if [[ -n "${CUBE_COMPOSE_OVERRIDE:-}" && -n "${COMPOSE_PROFILES:-}" ]]; then
        (cd "$demo_dir" && "${compose[@]}" --env-file "$env_file" \
            -f compose.yaml -f "$CUBE_COMPOSE_OVERRIDE" \
            --profile "$COMPOSE_PROFILES" "$@")
    elif [[ -n "${CUBE_COMPOSE_OVERRIDE:-}" ]]; then
        (cd "$demo_dir" && "${compose[@]}" --env-file "$env_file" \
            -f compose.yaml -f "$CUBE_COMPOSE_OVERRIDE" "$@")
    elif [[ -n "${COMPOSE_PROFILES:-}" ]]; then
        (cd "$demo_dir" && "${compose[@]}" --env-file "$env_file" -f compose.yaml \
            --profile "$COMPOSE_PROFILES" "$@")
    else
        (cd "$demo_dir" && "${compose[@]}" --env-file "$env_file" -f compose.yaml "$@")
    fi
}

wait_for_postgres() {
    for _ in {1..60}; do
        if run_compose exec -T postgres \
            pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" >/dev/null 2>&1; then
            return
        fi
        sleep 0.5
    done
    echo "PostgreSQL did not become ready within 30 seconds." >&2
    return 1
}

wait_for_cube() {
    for _ in {1..180}; do
        if curl --max-time 2 -fsS "http://127.0.0.1:${CUBE_PORT}/readyz" >/dev/null 2>&1; then
            return
        fi
        sleep 0.5
    done
    echo "Cube did not become ready within 90 seconds." >&2
    run_compose logs cube >&2
    return 1
}

verify() {
    wait_for_postgres
    wait_for_cube
    echo "Cube Playground: http://127.0.0.1:${CUBE_PORT}"
    echo "Shared Cube and PostgreSQL services are ready."
}

case "${1:-start}" in
    start)
        run_compose up -d
        verify
        ;;
    verify)
        verify
        ;;
    logs)
        run_compose logs -f cube postgres
        ;;
    stop)
        run_compose down
        ;;
    reset)
        run_compose down --volumes
        run_compose up -d
        verify
        ;;
    *)
        echo "Usage: $0 [start|verify|logs|stop|reset]" >&2
        exit 2
        ;;
esac
