#!/bin/sh
# Run as PUID:PGID (Unraid default nobody:users = 99:100) so files in appdata stay editable.
set -e

PUID=${PUID:-99}
PGID=${PGID:-100}
umask "${UMASK:-022}"

if [ "$(id -u)" = "0" ]; then
  if ! getent group "$PGID" >/dev/null 2>&1; then
    groupadd -o -g "$PGID" steep
  fi
  if ! getent passwd "$PUID" >/dev/null 2>&1; then
    useradd -o -u "$PUID" -g "$PGID" -d /data -s /usr/sbin/nologin steep
  fi
  mkdir -p "${STEEP_DATA_DIR:-/data}"
  chown -R "$PUID:$PGID" "${STEEP_DATA_DIR:-/data}"
  exec gosu "$PUID:$PGID" "$@"
fi

exec "$@"
