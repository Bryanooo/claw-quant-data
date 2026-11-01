#!/usr/bin/env bash
set -euo pipefail

# Run the factor publication integration suite against an isolated database.
# Deliberately do not override DB_NAME on `docker compose run`: Compose applies
# that interpolation to the postgres service too and may recreate the live
# container.  Instead, clone only the live schema inside the existing server.
test_database="${CLAW_FACTOR_TEST_DB:-claw_factor_migration_test_local}"
case "$test_database" in
  claw_factor_migration_test_*) ;;
  *)
    echo "refusing unsafe test database name: $test_database" >&2
    exit 2
    ;;
esac

docker compose exec -T postgres sh -lc '
  set -eu
  test_database="$1"
  dropdb --if-exists --force -U "$POSTGRES_USER" "$test_database"
  createdb -U "$POSTGRES_USER" "$test_database"
  pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
    --schema-only --no-owner --no-privileges \
    | psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" \
        -d "$test_database" >/dev/null
' sh "$test_database"

CLAW_FACTOR_TEST_DB="$test_database" \
  .venv/bin/pytest -q tests/test_feature_ownership_postgres.py
