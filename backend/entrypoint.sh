#!/bin/sh
# Copy SSH keys from the read-only mount to a writable location with correct
# ownership. The mounted volume is owned by the host user, which the container's
# appuser (UID 1001) can't read when the keys are chmod 600.
set -e

SRC="${SSH_KEYS_DIR_MOUNT:-/app/ssh_keys_mount}"
DST="${SSH_KEYS_DIR:-/app/ssh_keys}"

if [ -d "$SRC" ] && [ "$(ls -A "$SRC" 2>/dev/null)" ]; then
    cp -a "$SRC"/* "$DST"/ 2>/dev/null || true
    chmod 600 "$DST"/* 2>/dev/null || true
fi

exec "$@"
