#!/bin/sh
# Copy SSH keys from the read-only mount to a writable location with correct
# ownership for appuser. Runs as root, then drops to appuser for the main process.
set -e

SRC="/app/ssh_keys_mount"
DST="/app/ssh_keys"

if [ -d "$SRC" ] && [ "$(ls -A "$SRC" 2>/dev/null)" ]; then
    cp "$SRC"/* "$DST"/ 2>/dev/null || true
    chown appuser:appgroup "$DST"/* 2>/dev/null || true
    chmod 600 "$DST"/* 2>/dev/null || true
fi

exec gosu appuser "$@"
