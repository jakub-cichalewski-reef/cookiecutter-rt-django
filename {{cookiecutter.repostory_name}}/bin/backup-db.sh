#!/bin/bash -eu
set -o pipefail
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
source "${SCRIPT_DIR}/common.sh"

check_env_vars DATABASE_URL

TARGET_FILENAME="db_dump_$(date +%Y-%m-%d_%H%M%S).sql.gz"
DOCKER_NETWORK=$(get_db_docker_network)

DUMP_DB_TO_STDOUT="docker run --rm --network $DOCKER_NETWORK postgres:14.0-alpine pg_dump -Z 9 -c --if-exists $DATABASE_URL"

if [ -n "${BACKUP_B2_BUCKET}" ]; then
  $DUMP_DB_TO_STDOUT | bin/backup-file-to-b2.sh - "${TARGET_FILENAME}"
else
  LOCAL_BACKUP_DIR=".backups"
  mkdir -p "$LOCAL_BACKUP_DIR"
  TARGET="$LOCAL_BACKUP_DIR/$TARGET_FILENAME"
  $DUMP_DB_TO_STDOUT > "$TARGET"

  if [ -n "${EMAIL_HOST:-}" ] && [ -n "${EMAIL_TARGET:-}" ]; then
    "${SCRIPT_DIR}"/backup-db-to-email.sh "${TARGET}"
  fi
fi

if [ -n "${BACKUP_LOCAL_ROTATE_KEEP_LAST:-}" ]; then
  echo "Rotating backup files - keeping ${BACKUP_LOCAL_ROTATE_KEEP_LAST} last ones"
  bin/rotate-local-backups.py "${BACKUP_LOCAL_ROTATE_KEEP_LAST}"
fi
