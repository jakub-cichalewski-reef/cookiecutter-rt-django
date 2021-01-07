#!/bin/bash -eu

if [ "$(basename "$0")" == 'bin' ]; then
  cd ..
fi

if [ -z "$1" ]; then
  echo "Pass backup file name/path (in B2) as the first argument"
  exit 127
fi

if [[ -z "$BACKUP_B2_BUCKET" || -z "$BACKUP_B2_KEY_ID" || -z "$BACKUP_B2_KEY_SECRET" ]]; then
  echo "Set BACKUP_B2_BUCKET, BACKUP_B2_KEY_ID and BACKUP_B2_KEY_SECRET env variables before running this script"
  exit 127
fi

CONTAINER_NAME="{{ cookiecutter.repostory_name }}-backups-b2"
docker build --quiet -t "$CONTAINER_NAME" tools/backup-b2

docker run \
  --mount type=bind,src="$(pwd)"/.backups,target=/root/.backups \
  --env BACKUP_B2_BUCKET \
  --env BACKUP_B2_KEY_ID \
  --env BACKUP_B2_KEY_SECRET \
  "$CONTAINER_NAME" ./retrieve_backup.sh "$1"

bin/restore-db.sh ".backups/$(basename "$1")"
