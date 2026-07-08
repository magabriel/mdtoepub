#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"

if [ "$1" = "debug" ]; then
    export MDTOEPUB_DEV=1
    shift
fi

exec env -i \
    HOME="$HOME" \
    USER="$USER" \
    LOGNAME="$LOGNAME" \
    DISPLAY="$DISPLAY" \
    WAYLAND_DISPLAY="$WAYLAND_DISPLAY" \
    XDG_RUNTIME_DIR="$XDG_RUNTIME_DIR" \
    XDG_SESSION_TYPE="$XDG_SESSION_TYPE" \
    DBUS_SESSION_BUS_ADDRESS="$DBUS_SESSION_BUS_ADDRESS" \
    GTK_MODULES="$GTK_MODULES" \
    GTK_IM_MODULE="$GTK_IM_MODULE" \
    LANG="$LANG" \
    LANGUAGE="$LANGUAGE" \
    LC_ALL="$LC_ALL" \
    PATH="/usr/local/bin:/usr/bin:/bin" \
    MDTOEPUB_DEV="${MDTOEPUB_DEV:-0}" \
    PYTHONDONTWRITEBYTECODE=1 \
    "$DIR/.venv/bin/python3" -m mdtoepub.main "$@"
