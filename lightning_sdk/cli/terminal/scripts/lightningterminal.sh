#!/usr/bin/env bash
#
# lightningterminal.sh — Terminal session management for Lightning Studios
#
# Manages persistent terminal sessions inside studios. Sessions survive
# disconnects and can be listed, attached, detached, and switched between.
# Also accessible as `lt` (a shell function defined in lightningterminal.rc).
#
# Portable across bash and zsh. The backend (currently GNU screen) is
# abstracted behind a thin interface — see "Backend dispatch" below.
#
# Quick reference:
#   lt ls                        List sessions
#   lt new --name "Backend"      Create a named session
#   lt attach --id <id>          Attach (creates if needed)
#   lt detach                    Detach from current session
#   lt kill --id <id>            Kill a session
#   lt status [--ancestors]      Show status / ancestor tree
#   Ctrl+T, D                    Detach (works even when terminal is busy)
#
# Session identification:
#   --id <session_id>   Stable programmatic identifier (e.g. "backend-a7f3b2c1").
#                       Matches [a-zA-Z0-9_-]+. Auto-generated from --name if
#                       not provided (sanitised name + random hex suffix).
#                       Use this in scripts and tooling.
#   --name <name>       User-facing label shown in ls/status output. Free-form
#                       text, not necessarily unique. Matches against the
#                       terminal_name or the default_name (term-1, term-2, ...).
#                       Use this for interactive lookups.
#
# Output format (--raw): key-value records, one field per line, separated
# by blank lines. Split on first ": " — values can contain colons.
#

set -euo pipefail

# In zsh, re-declaring `local` on an existing variable prints its current value
# to stdout — e.g. `local x` inside a loop prints `x=old_value` on the second
# iteration. TYPESET_SILENT suppresses this. The primary fix is hoisting locals
# out of loops, but this guards against any we miss.
[ -n "${ZSH_VERSION:-}" ] && setopt TYPESET_SILENT 2>/dev/null || true

# --- Configuration ---

BACKEND="${LIGHTNING_TERMINAL_BACKEND:-screen}"
SCRIPT_NAME="${LIGHTNING_TERMINAL_HELP_SCRIPT_NAME:-lightningterminal.sh}"

# Metadata directory — set after backend-specific config computes the base dir.
# Backends set META_DIR in their config section; the default is computed below
# if no backend overrides it.

# --- Index counter ---

# Return the next session index and increment the counter.
# Indexes are 1-based, never reused (gaps are fine).
# Uses flock for atomic read-increment-write to prevent races
# when multiple sessions are created concurrently.
# The counter file lives in the metadata directory on tmpfs,
# so it resets on reboot along with the sessions.
_next_index() {
    local index_file="$META_DIR/.next_index"
    (
        flock 9
        local next=1
        if [ -f "$index_file" ]; then
            next=$(cat "$index_file")
        fi
        echo "$next"
        echo $((next + 1)) > "$index_file"
    ) 9>"${index_file}.lock"
}

# --- Metadata helpers ---
#
# Metadata is stored as key-value files in the metadata directory.
# Format matches our output format: "key: value" per line.
# No JSON — avoids escaping issues and doesn't require jq.

# Read a single field from a session's metadata file.
# Usage: _read_meta <session_id> <field_name>
# Outputs the field value, or empty string if not found.
_read_meta() {
    local meta_file="$META_DIR/${1}.meta"
    if [ -f "$meta_file" ]; then
        local line
        line=$(grep "^${2}: " "$meta_file" 2>/dev/null || true)
        if [ -n "$line" ]; then
            echo "${line#*: }"
        fi
    fi
}

# Load all metadata fields from a session's .meta file into _meta_* variables.
# Much faster than calling _read_meta per field (one file read vs N greps).
# Sets: _meta_name, _meta_created, _meta_index, _meta_source, _meta_delegated_to
_load_meta() {
    _meta_name=""
    _meta_created=""
    _meta_index=""
    _meta_source=""
    _meta_delegated_to=""
    local meta_file="$META_DIR/${1}.meta"
    if [ -f "$meta_file" ]; then
        local key value
        while IFS= read -r line || [ -n "$line" ]; do
            key="${line%%: *}"
            value="${line#*: }"
            case "$key" in
                name)           _meta_name="$value" ;;
                created)        _meta_created="$value" ;;
                index)          _meta_index="$value" ;;
                source)         _meta_source="$value" ;;
                delegated_to)   _meta_delegated_to="$value" ;;
            esac
        done < "$meta_file"
    fi
}

# Write a metadata file for a session.
# Allocates a new index for default_name (term-<index>).
# Usage: _write_meta <session_id> <terminal_name> [<source>] [<created_timestamp>]
_write_meta() {
    local meta_file="$META_DIR/${1}.meta"
    local name="$2"
    local source="${3:-}"
    local created="${4:-$(date -u +%Y-%m-%dT%H:%M:%S.%N+00:00)}"
    local index
    index=$(_next_index)
    {
        echo "name: $name"
        echo "created: $created"
        echo "index: $index"
        if [ -n "$source" ]; then
            echo "source: $source"
        fi
    } > "$meta_file"
}

# Delete the metadata and history files for a session.
# Usage: _delete_meta <session_id>
_delete_meta() {
    local meta_dir
    meta_dir=$META_DIR
    rm -f "${meta_dir}/${1}.meta"
    rm -f "${meta_dir}/${1}.history"
}

# Read the last command executed in a session.
# Reads from the .history file in the metadata directory, written by
# lightningterminal.rc's preexec hook.
# Usage: _last_command <pid> <session_id>
# Outputs the last line of the history file (truncated to 200 chars), or empty.
_last_command() {
    local pid="$1"
    local session_id="$2"
    local history_file="$META_DIR/${session_id}.history"
    if [ -f "$history_file" ]; then
        # Read last line without forking tail/head
        local last="" line
        while IFS= read -r line || [ -n "$line" ]; do
            last="$line"
        done < "$history_file"
        echo "${last:0:200}"
    fi
}

# --- ID generation ---

# Sanitise a string for use as a session ID component.
# Lowercases, replaces spaces/special chars with hyphens, strips leading/trailing hyphens.
# "My Backend!" → "my-backend"
_sanitise_name() {
    echo "$1" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9-' '-' | sed 's/^-//;s/-$//'
}

# Validate a session ID. Only allows [a-zA-Z0-9_-] to avoid issues with
# backend socket filenames, grep patterns, and output parsing.
_validate_session_id() {
    local id="$1"
    if [ -z "$id" ]; then
        echo "error: session_id cannot be empty" >&2
        return 1
    fi
    case "$id" in
        *[!a-zA-Z0-9_-]*)
            echo "error: session_id '$id' contains invalid characters (only a-z, A-Z, 0-9, _, - allowed)" >&2
            return 1
            ;;
    esac
}

# Generate a unique session ID from a human-readable name.
# Format: <sanitised-name>-<8 random hex chars>, e.g. "backend-a7f3b2c1".
# 8 hex chars = 4 bytes = ~4 billion possibilities, sufficient to avoid collisions.
_generate_session_id() {
    local name
    name=$(_sanitise_name "$1")
    if [ -z "$name" ]; then
        name="session"
    fi
    local suffix
    suffix=$(head -c 4 /dev/urandom | od -An -tx1 | tr -d ' ')
    echo "${name}-${suffix}"
}

# --- Output helpers ---

# Emit a key-value field. Always outputs "key: value" format.
# Empty values output "key: " (with trailing space) so parsers
# can always split on first ": ".
# Usage: _emit "key" "value"
_emit() {
    echo "${1}: ${2:-}"
}

# Compute a human-readable display label from terminal_name, default_name, and last_command.
# Format: "Name (command)" or "Name" or "term-PID (command)" or "term-PID"
# Usage: _display_label <terminal_name> <default_name> <last_command>
_display_label() {
    local terminal_name="$1"
    local default_name="$2"
    local last_command="$3"
    local name="${terminal_name:-$default_name}"

    if [ -n "$last_command" ] && [ "$last_command" != "$name" ]; then
        echo "${name} (${last_command})"
    else
        echo "$name"
    fi
}

# Format a session as a human-readable one-liner.
# Format: "Name - last_command (status, id=session_id)"
# Usage: _format_oneliner <terminal_name> <default_name> <last_cmd> <status> <session_id>
_format_oneliner() {
    local terminal_name="$1"
    local default_name="$2"
    local last_cmd="$3"
    local session_status="$4"
    local session_id="$5"
    local name="${terminal_name:-$default_name}"

    local line="$name"
    if [ -n "$last_cmd" ] && [ "$last_cmd" != "$name" ]; then
        line="$line - $last_cmd"
    fi
    line="$line ($session_status, id=$session_id)"
    echo "$line"
}

# =====================================================================
# Backend: screen
# =====================================================================
#
# GNU screen backend. Each _screen__* function implements one backend
# primitive using screen commands. These are the ONLY functions that
# interact with the screen binary or read the socket directory.
#
# --- Integration with .lightningrc ---
#
# In production studios, /settings/.lightningrc creates screen sessions when
# a terminal is opened. The platform sets LAI_TERM_SESSION_NAME on the SSH
# session before the shell starts. To migrate, replace the screen block with:
#
#   exec lightningterminal.sh attach --id "$LAI_TERM_SESSION_NAME" --exec \
#       ${LAI_TERM_SOURCE:+--source "$LAI_TERM_SOURCE"}
#
# This single line replaces the old create/restore logic. The attach command
# creates the session if it doesn't exist, or reattaches if it does — so
# the LAI_TERM_RESTORE flag is no longer needed.
#
# The inner shell sources lightningterminal.rc, which detects it's
# inside a session via LIGHTNING_TERMINAL_SESSION_ID (set by the parent) and
# installs command tracking hooks + terminal fixes:
#
#   source /settings/lightningterminal.rc

# --- Screen configuration ---

SCREENRC="${LIGHTNING_TERMINAL_SCREENRC:-}"
SCREEN_DIR="${LIGHTNING_TERMINAL_SCREENDIR:-/run/screen/S-$(whoami)}"
META_DIR="${LIGHTNING_TERMINAL_DIR:-${SCREEN_DIR}/.terminal-meta}"

# Aligns with _screen__setup which creates a symlink from /settings/shell to screen
_shell_base="${SHELL:-bash}"
_shell_base="${_shell_base##*/}"
if [ -f "/settings/${_shell_base}" ]; then
    SCREEN_BIN="/settings/${_shell_base}"
else
    SCREEN_BIN="screen"
fi
unset _shell_base

# Ensure the metadata directory exists.
mkdir -p "$META_DIR" 2>/dev/null || true

# Returns the screenrc path to use when creating new sessions.
# Priority: env override > studio default > user default > none.
_screenrc() {
    if [ -n "$SCREENRC" ]; then
        echo "$SCREENRC"
    elif [ -f /settings/.screenrc ]; then
        echo /settings/.screenrc
    elif [ -f "$HOME/.screenrc" ]; then
        echo "$HOME/.screenrc"
    fi
}

# Run a screen command with the correct SCREENDIR and binary.
_screen__cmd() {
    env SCREENDIR="$SCREEN_DIR" "$SCREEN_BIN" "$@"
}

# --- Backend primitives ---

# Ensure the screen socket directory exists with correct permissions.
# Creates the /settings/$SHELL symlink so screen shows as the user's shell.
# Idempotent — safe to call multiple times.
# Skipped when LIGHTNING_TERMINAL_SKIP_SETUP=1 (e.g. in tests).
_screen__setup() {
    if [ -n "${LIGHTNING_TERMINAL_SKIP_SETUP:-}" ]; then
        return 0
    fi
    local sdir
    sdir="$SCREEN_DIR"
    if [ ! -d "$sdir" ]; then
        if [ "$sdir" = "/run/screen/S-$(whoami)" ] || [ "$sdir" = "/var/run/screen/S-$(whoami)" ]; then
            sudo mkdir -p /var/run/screen 2>/dev/null || true
            sudo chmod 0777 /var/run/screen 2>/dev/null || true
        fi
        mkdir -p "$sdir" 2>/dev/null || true
    fi

    local shell_name
    shell_name=$(basename "${SHELL:-bash}")
    if [ -d /settings ] && [ ! -f "/settings/${shell_name}" ]; then
        sudo ln -s /usr/bin/screen "/settings/${shell_name}" 2>/dev/null || true
    fi
}

# Enumerate all live screen sessions.
# Output: tab-delimited lines: pid\tsession_id\tstatus
# Status is "attached" or "detached". Dead sessions are excluded.
# Wipes dead sessions before listing.
_screen__list_sessions() {
    _screen__cmd -wipe > /dev/null 2>&1 || true
    local output
    output=$(_screen__cmd -ls 2>&1 || true)

    local trimmed pid session_id session_status
    while IFS= read -r line; do
        case "$line" in
            *[0-9].*)
                trimmed="${line#"${line%%[! 	]*}"}"
                pid="${trimmed%%.*}"
                local rest="${trimmed#*.}"
                session_id="${rest%%	*}"

                session_status=""
                case "$line" in
                    *[Aa]ttached*) session_status="attached" ;;
                    *[Dd]etached*) session_status="detached" ;;
                    *) continue ;;
                esac

                printf '%s\t%s\t%s\n' "$pid" "$session_id" "$session_status"
                ;;
        esac
    done <<< "$output"
}

# Check if a session exists by looking for its socket.
# Output: the PID on stdout, or empty if not found.
_screen__session_exists() {
    local session_id="$1"
    local match
    match=$(ls "$SCREEN_DIR/" 2>/dev/null | grep "\.${session_id}$" | head -1) || true
    if [ -n "$match" ]; then
        echo "${match%%.*}"
    fi
}

# Get the creation time of a screen socket file as an ISO timestamp.
# Uses stat's birth time (statx syscall, Linux 4.11+). Falls back to empty.
_screen__session_created() {
    local session_id="$1"
    local match
    match=$(ls "$SCREEN_DIR/" 2>/dev/null | grep "\.${session_id}$" | head -1) || true
    if [ -n "$match" ]; then
        local ts
        ts=$(stat --format=%W "$SCREEN_DIR/$match" 2>/dev/null || echo "0")
        if [ "$ts" != "0" ] && [ -n "$ts" ]; then
            date -u -d "@$ts" +%Y-%m-%dT%H:%M:%S+00:00 2>/dev/null || true
        fi
    fi
}

# Create a detached screen session with standard config.
# Sets env vars for the inner shell so it can identify itself.
_screen__create() {
    local session_id="$1"
    local sdir="$SCREEN_DIR"

    # Check socket path length — Unix sockets are limited to ~108 chars.
    local max_socket_path=108
    local estimated_len=$(( ${#sdir} + 1 + 7 + 1 + ${#session_id} ))
    if [ "$estimated_len" -gt "$max_socket_path" ]; then
        echo "error: socket path too long (${estimated_len} > ${max_socket_path} chars)." >&2
        echo "error: reduce LIGHTNING_TERMINAL_SCREENDIR path or session_id length." >&2
        exit 1
    fi

    local rc
    rc=$(_screenrc)
    local shell="${SHELL:-bash}"
    local history_file="${META_DIR}/${session_id}.history"

    if [ -n "$rc" ]; then
        env SCREENDIR="$SCREEN_DIR" \
            LIGHTNING_TERMINAL_SESSION_ID="$session_id" \
            LIGHTNING_TERMINAL_LAST_COMMAND_FILE="$history_file" \
            "$SCREEN_BIN" -dmS "$session_id" -c "$rc" "$shell"
    else
        env SCREENDIR="$SCREEN_DIR" \
            LIGHTNING_TERMINAL_SESSION_ID="$session_id" \
            LIGHTNING_TERMINAL_LAST_COMMAND_FILE="$history_file" \
            "$SCREEN_BIN" -dmS "$session_id" "$shell"
    fi
    _screen__cmd -S "$session_id" -X scrollback 5000 2>/dev/null || true

    if [ -z "${LIGHTNING_TERMINAL_SKIP_MULTIUSER:-}" ]; then
        _screen__cmd -S "$session_id" -X multiuser on 2>/dev/null || true
        _screen__cmd -S "$session_id" -X acladd zeus 2>/dev/null || true
        _screen__cmd -S "$session_id" -X acladd "$(whoami)" 2>/dev/null || true
    fi

    # Register Ctrl+T, D / Ctrl+T, Ctrl+D as detach shortcuts. Works even
    # when a process is consuming stdin, because screen intercepts it at
    # the multiplexer level. Ctrl+T, Ctrl+T sends a literal Ctrl+T (for
    # readline's transpose-chars).
    #
    # When delegating to a nested session, _session_attach temporarily
    # removes these bindings so the key sequence passes through to the
    # inner session. See _screen__bind_detach_key / _screen__unbind_detach_key.
    _screen__bind_detach_key "$session_id"
    _screen__cmd -S "$session_id" -X bindkey "^t^t" stuff "^t" 2>/dev/null || true

    # Initialise command history with the shell name (e.g. "zsh", "bash").
    echo "${shell##*/}" > "$history_file" 2>/dev/null || true
}

# Attach to an existing screen session.
# Args: session_id, use_exec ("1" or ""), use_nice ("1" or "")
# With use_exec: replaces this process (exec).
# Without use_exec: runs screen as a child (blocking).
_screen__attach() {
    local session_id="$1"
    local use_exec="${2:-}"
    local use_nice="${3:-}"

    if [ "$use_exec" = "1" ]; then
        if [ "$use_nice" = "1" ]; then
            exec nice -n 20 env SCREENDIR="$SCREEN_DIR" "$SCREEN_BIN" -x "$session_id"
        else
            exec env SCREENDIR="$SCREEN_DIR" "$SCREEN_BIN" -x "$session_id"
        fi
    fi

    # Non-exec: run as child
    if [ "$use_nice" = "1" ]; then
        nice -n 20 env SCREENDIR="$SCREEN_DIR" "$SCREEN_BIN" -x "$session_id"
    else
        _screen__cmd -x "$session_id"
    fi
}

# Detach the current client from a screen session.
_screen__detach() {
    local session_id="$1"
    _screen__cmd -S "$session_id" -X detach
}

# Send keystrokes to a screen session.
_screen__send() {
    local session_id="$1"
    shift
    local command="$*"
    _screen__cmd -S "$session_id" -X stuff "${command}
"
}

# Read the full scrollback buffer of a screen session.
_screen__read_buffer() {
    local session_id="$1"
    local tmpfile
    tmpfile=$(mktemp /tmp/lt-hardcopy.XXXXXX)
    _screen__cmd -S "$session_id" -X hardcopy -h "$tmpfile" 2>/dev/null
    local tries=0
    while [ ! -s "$tmpfile" ] && [ "$tries" -lt 50 ]; do
        sleep 0.01
        tries=$((tries + 1))
    done
    sed '/[^[:space:]]/,$!d' "$tmpfile"
    rm -f "$tmpfile"
}

# Kill a screen session's server process. Does NOT delete metadata.
_screen__kill() {
    local session_id="$1"
    _screen__cmd -S "$session_id" -X quit 2>/dev/null || true
}

# Register Ctrl+T detach bindings on a session.
_screen__bind_detach_key() {
    local session_id="$1"
    _screen__cmd -S "$session_id" -X bindkey "^td" detach 2>/dev/null || true
    _screen__cmd -S "$session_id" -X bindkey "^t^d" detach 2>/dev/null || true
}

# Remove Ctrl+T detach bindings from a session, so the key sequence
# passes through to a nested inner session instead.
# In screen, calling `bindkey` with a string and no command removes the binding.
_screen__unbind_detach_key() {
    local session_id="$1"
    _screen__cmd -S "$session_id" -X bindkey "^td" 2>/dev/null || true
    _screen__cmd -S "$session_id" -X bindkey "^t^d" 2>/dev/null || true
}

# =====================================================================
# Backend dispatch
# =====================================================================
#
# Maps _backend_* to the active backend's implementation.
# Adding a new backend means adding a case branch here and
# implementing each _<backend>__* function.

case "$BACKEND" in
    screen)
        _backend_setup()            { _screen__setup "$@"; }
        _backend_list_sessions()    { _screen__list_sessions "$@"; }
        _backend_session_exists()   { _screen__session_exists "$@"; }
        _backend_session_created()  { _screen__session_created "$@"; }
        _backend_create()           { _screen__create "$@"; }
        _backend_attach()           { _screen__attach "$@"; }
        _backend_detach()           { _screen__detach "$@"; }
        _backend_send()             { _screen__send "$@"; }
        _backend_read_buffer()      { _screen__read_buffer "$@"; }
        _backend_kill()             { _screen__kill "$@"; }
        _backend_bind_detach_key()  { _screen__bind_detach_key "$@"; }
        _backend_unbind_detach_key() { _screen__unbind_detach_key "$@"; }
        ;;
    *)
        echo "error: unknown backend: $BACKEND" >&2
        exit 1
        ;;
esac

# =====================================================================
# Session operations (backend-agnostic)
# =====================================================================
#
# These functions implement all orchestration logic — metadata,
# delegation tracking, ancestor walks, name resolution, formatting.
# They call _backend_* primitives for raw session operations.

# Verify a session exists, or exit with a user-friendly error.
_require_session() {
    local pid
    pid=$(_backend_session_exists "$1")
    if [ -z "$pid" ]; then
        echo "error: no terminal session found with session_id '$1'" >&2
        exit 1
    fi
}

# List all live sessions with metadata enrichment.
# Args: mode — "oneliner" (default) or "raw" (key-value records)
_session_list() {
    local mode="${1:-oneliner}"
    _backend_setup

    local pid session_id session_status created
    local entries=""
    while IFS='	' read -r pid session_id session_status; do
        [ -z "$session_id" ] && continue
        _load_meta "$session_id"
        created="${_meta_created}"
        if [ -z "$created" ]; then
            created=$(_backend_session_created "$session_id")
        fi
        entries="${entries}${created}	${pid}	${session_id}	${session_status}
"
    done <<< "$(_backend_list_sessions)"

    [ -z "$entries" ] && return 0

    # Sort by created date (ISO, lexicographic) then PID as tiebreaker.
    local sorted
    sorted=$(echo "$entries" | sort -t'	' -k1,1 -k2,2n)

    local last_cmd default_name label
    while IFS='	' read -r created pid session_id session_status; do
        [ -z "$session_id" ] && continue
        _load_meta "$session_id"
        last_cmd=$(_last_command "$pid" "$session_id")
        default_name="term-${_meta_index:-$pid}"

        if [ "$mode" = "raw" ]; then
            label=$(_display_label "$_meta_name" "$default_name" "$last_cmd")
            _emit "session_id" "$session_id"
            _emit "pid" "$pid"
            _emit "status" "$session_status"
            _emit "terminal_name" "$_meta_name"
            _emit "default_name" "$default_name"
            _emit "display_label" "$label"
            _emit "last_command" "$last_cmd"
            _emit "created" "${_meta_created:-$created}"
            if [ -n "$_meta_source" ]; then
                _emit "source" "$_meta_source"
            fi
            if [ -n "$_meta_delegated_to" ]; then
                _emit "delegated_to" "$_meta_delegated_to"
            fi
            echo ""
        else
            _format_oneliner "$_meta_name" "$default_name" "$last_cmd" "$session_status" "$session_id"
        fi
    done <<< "$sorted"
}

# Resolve a target identifier to a session_id.
# Searches across terminal_name (metadata), default_name (term-<N>),
# PID, and session_id. Can be restricted to a specific field with --by.
#
# Usage: _session_resolve <by> <target>
#   by: "any", "any_name", "terminal_name", "default_name", "pid", "session_id"
# Output: session_id on stdout, or exit 1 if not found.
_session_resolve() {
    local by="$1"
    local target="$2"

    # Collect all matches — we need to detect ambiguity.
    local matches="" match_count=0
    local pid session_id terminal_name default_name matched last_cmd

    while IFS='	' read -r pid session_id session_status; do
        [ -z "$session_id" ] && continue
        _load_meta "$session_id"
        terminal_name="$_meta_name"
        default_name="term-${_meta_index:-$pid}"

        matched=0
        case "$by" in
            terminal_name)  [ "$terminal_name" = "$target" ] && matched=1 ;;
            default_name)   [ "$default_name" = "$target" ] && matched=1 ;;
            any_name)
                [ "$terminal_name" = "$target" ] && matched=1
                [ "$matched" = "0" ] && [ "$default_name" = "$target" ] && matched=1
                ;;
            pid)            [ "$pid" = "$target" ] && matched=1 ;;
            session_id)     [ "$session_id" = "$target" ] && matched=1 ;;
            any)
                [ "$terminal_name" = "$target" ] && matched=1
                [ "$matched" = "0" ] && [ "$default_name" = "$target" ] && matched=1
                [ "$matched" = "0" ] && [ "$pid" = "$target" ] && matched=1
                [ "$matched" = "0" ] && [ "$session_id" = "$target" ] && matched=1
                ;;
            *)
                echo "error: unknown field: $by" >&2
                exit 1
                ;;
        esac

        if [ "$matched" = "1" ]; then
            match_count=$((match_count + 1))
            if [ "$match_count" = "1" ]; then
                matches="$session_id"
            else
                matches="${matches}
$session_id"
            fi
        fi
    done <<< "$(_backend_list_sessions)"

    if [ "$match_count" = "1" ]; then
        echo "$matches"
        return 0
    fi

    if [ "$match_count" -gt 1 ]; then
        echo "error: multiple sessions match '$target'" >&2
        local sid
        while IFS= read -r sid; do
            [ -z "$sid" ] && continue
            echo "  $(_session_status "$sid" "oneliner")" >&2
        done <<< "$matches"
        echo "Use --id to specify which session." >&2
        exit 1
    fi

    echo "error: no session found matching '$target'" >&2
    exit 1
}

# Create a new session (detached) and output its record.
# Args: session_id (optional), terminal_name (optional), source (optional)
# Output: single record with session_id, pid, status, terminal_name
_session_new() {
    _backend_setup
    local session_id="$1"
    local terminal_name="$2"
    local source="${3:-}"

    if [ -z "$session_id" ]; then
        if [ -n "$terminal_name" ]; then
            session_id=$(_generate_session_id "$terminal_name")
        else
            session_id=$(_generate_session_id "session")
        fi
    else
        _validate_session_id "$session_id" || exit 1
    fi

    # Check for duplicate session_id
    local existing_pid
    existing_pid=$(_backend_session_exists "$session_id")
    if [ -n "$existing_pid" ]; then
        echo "error: session '$session_id' already exists" >&2
        exit 1
    fi

    _backend_create "$session_id"
    _write_meta "$session_id" "$terminal_name" "$source"

    local pid
    pid=$(_backend_session_exists "$session_id")

    _emit "session_id" "$session_id"
    _emit "pid" "${pid:-unknown}"
    _emit "status" "detached"
    _emit "terminal_name" "$terminal_name"
}

# Send a command to a session.
_session_send() {
    local session_id="$1"
    shift
    local command="$*"
    _require_session "$session_id"
    _backend_send "$session_id" "$command"
}

# Read the scrollback buffer of a session.
_session_read() {
    local session_id="$1"
    _require_session "$session_id"
    _backend_read_buffer "$session_id"
}

# Kill a session and remove its metadata.
_session_kill() {
    local session_id="$1"
    _require_session "$session_id"
    _backend_kill "$session_id"
    _delete_meta "$session_id"
}

# Show status of a specific session.
# Args: session_id, mode ("oneliner" or "raw")
_session_status() {
    local session_id="$1"
    local mode="${2:-oneliner}"
    _require_session "$session_id"

    local raw_output
    raw_output=$(_session_list "raw")
    local record
    record=$(echo "$raw_output" | awk -v sid="$session_id" '
        /^session_id: / { current_sid = substr($0, 13) }
        current_sid == sid { print }
        current_sid == sid && /^$/ { exit }
    ')

    if [ "$mode" = "raw" ]; then
        echo "$record"
    else
        local terminal_name default_name last_cmd session_status
        terminal_name=$(echo "$record" | grep "^terminal_name: " | head -1 | sed 's/^terminal_name: //')
        default_name=$(echo "$record" | grep "^default_name: " | head -1 | sed 's/^default_name: //')
        last_cmd=$(echo "$record" | grep "^last_command: " | head -1 | sed 's/^last_command: //')
        session_status=$(echo "$record" | grep "^status: " | head -1 | sed 's/^status: //')
        _format_oneliner "$terminal_name" "$default_name" "$last_cmd" "$session_status" "$session_id"
    fi
}

# Rename a session's terminal_name in metadata.
_session_rename() {
    local session_id="$1"
    local new_name="$2"
    _require_session "$session_id"

    local meta_file="$META_DIR/${session_id}.meta"
    if [ -f "$meta_file" ]; then
        if grep -q "^name: " "$meta_file" 2>/dev/null; then
            sed -i "s/^name: .*/name: $new_name/" "$meta_file"
        else
            echo "name: $new_name" >> "$meta_file"
        fi
    else
        _write_meta "$session_id" "$new_name"
    fi
}

# Detach from the current session.
_session_detach() {
    local session_id="${LIGHTNING_TERMINAL_SESSION_ID:-}"
    if [ -z "$session_id" ]; then
        echo "error: not inside a session (LIGHTNING_TERMINAL_SESSION_ID not set)" >&2
        exit 1
    fi
    _require_session "$session_id"
    _backend_detach "$session_id"
}

# Read the last command for a session.
_session_last_command() {
    local session_id="$1"
    local pid
    pid=$(_backend_session_exists "$session_id")
    if [ -n "$pid" ]; then
        _last_command "$pid" "$session_id"
    fi
}

# Attach to an existing session with delegation tracking.
# The backend just does the raw attach; this function handles
# the require check, metadata write, and delegation lifecycle.
#
# Args: session_id, use_exec ("1" or ""), terminal_name (optional)
_session_attach() {
    local session_id="$1"
    local use_exec="${2:-}"
    local terminal_name="${3:-}"
    _require_session "$session_id"

    if [ -n "$terminal_name" ]; then
        _write_meta "$session_id" "$terminal_name"
    fi

    local use_nice=""
    [ -z "${LIGHTNING_TERMINAL_SKIP_NICE:-}" ] && use_nice="1"

    if [ "$use_exec" = "1" ]; then
        # Replace this process — no delegation tracking needed
        _backend_attach "$session_id" "1" "$use_nice"
        # (never returns — exec replaced the process)
    fi

    # Print detach hint for interactive attach (non-exec, stdout is a tty)
    if [ -t 1 ] && [ -z "${LIGHTNING_TERMINAL_QUIET:-}" ]; then
        echo "── Tip: detach with Ctrl+T, D (or $SCRIPT_NAME detach) ──" >&2
        echo "" >&2
    fi

    # Non-exec attach: delegation tracking + detach key management
    local current_session="${LIGHTNING_TERMINAL_SESSION_ID:-}"
    local meta_file=""
    if [ -n "$current_session" ]; then
        meta_file="$META_DIR/${current_session}.meta"
        if [ -f "$meta_file" ]; then
            echo "delegated_to: $session_id" >> "$meta_file"
            # Unbind detach key on outer session so Ctrl+T, D passes
            # through to the inner session we're about to attach to.
            _backend_unbind_detach_key "$current_session" 2>/dev/null || true
            trap '
                sed -i "/^delegated_to: /d" "'"$meta_file"'"
                _backend_bind_detach_key "'"$current_session"'" 2>/dev/null || true
            ' EXIT INT TERM
        fi
    fi

    _backend_attach "$session_id" "" "$use_nice"

    # Clean up delegation and restore detach key (also handled by trap, but be explicit)
    if [ -n "$meta_file" ] && [ -f "$meta_file" ]; then
        sed -i '/^delegated_to: /d' "$meta_file"
        _backend_bind_detach_key "$current_session" 2>/dev/null || true
        trap - EXIT INT TERM
    fi
}

# Resolve, create-if-needed, and attach to a session.
# Handles --id, --name, --exec, --no-create, --source logic.
_session_attach_or_create() {
    local session_id="$1"
    local terminal_name="$2"
    local use_exec="$3"
    local no_create="$4"
    local source="${5:-}"

    # Resolve --name to a session_id if no --id was given.
    if [ -z "$session_id" ] && [ -n "$terminal_name" ]; then
        session_id=$(_session_resolve "any_name" "$terminal_name" 2>/dev/null) || true
    fi

    # Guard: refuse to attach to the current session or any ancestor.
    if [ -n "$session_id" ]; then
        local ancestor_ids
        ancestor_ids=$(_session_ancestors 2>/dev/null | grep "^session_id: " | sed 's/^session_id: //') || true
        if [ -n "$ancestor_ids" ]; then
            while IFS= read -r ancestor_id; do
                [ -z "$ancestor_id" ] && continue
                if [ "$session_id" = "$ancestor_id" ]; then
                    echo "error: cannot attach to session '$session_id' — already inside it (or an ancestor)" >&2
                    exit 1
                fi
            done <<< "$ancestor_ids"
        fi
    fi

    if [ -n "$session_id" ]; then
        local pid
        pid=$(_backend_session_exists "$session_id")
        if [ -z "$pid" ]; then
            if [ "$no_create" = "1" ]; then
                echo "error: no terminal session found with id '$session_id'" >&2
                exit 1
            fi
            _backend_setup
            _backend_create "$session_id"
            _write_meta "$session_id" "$terminal_name" "$source"
        fi
    else
        if [ "$no_create" = "1" ]; then
            echo "error: --id or --name is required with --no-create" >&2
            exit 1
        fi
        _backend_setup
        if [ -n "$terminal_name" ]; then
            session_id=$(_generate_session_id "$terminal_name")
        else
            session_id=$(_generate_session_id "session")
        fi
        _backend_create "$session_id"
        _write_meta "$session_id" "$terminal_name" "$source"
    fi

    _session_attach "$session_id" "$use_exec"
}

# Walk the ancestor delegation tree from a given session via DFS.
# Builds a reverse map (child → parents) from metadata, then walks
# upward. Outputs "session_id depth" lines in DFS order. Verifies
# each session still exists before including it.
#
# Args: session_id
# Output: "session_id depth" lines, one per ancestor (root session at depth 0)
# Exit: 0 if at least one session found, 1 otherwise.
_session_ancestor_walk() {
    local current="$1"
    if [ -z "$current" ]; then
        return 1
    fi

    local current_pid
    current_pid=$(_backend_session_exists "$current" 2>/dev/null) || true
    if [ -z "$current_pid" ]; then
        return 1
    fi

    # Build reverse map: scan all .meta files once.
    local reverse_map=""
    local meta_file
    for meta_file in "$META_DIR"/*.meta; do
        [ -f "$meta_file" ] || continue
        local parent_id
        parent_id=$(basename "$meta_file" .meta)
        local delegated_to
        delegated_to=$(grep "^delegated_to: " "$meta_file" 2>/dev/null | sed 's/^delegated_to: //') || true
        if [ -n "$delegated_to" ]; then
            reverse_map="${reverse_map:+$reverse_map
}$delegated_to $parent_id"
        fi
    done

    # DFS via explicit stack. Each entry is "session_id depth".
    local stack="$current 0"
    local seen=" $current "
    local found_any=0

    while [ -n "$stack" ]; do
        local top
        top=$(echo "$stack" | tail -1)
        stack=$(echo "$stack" | sed '$d')
        stack=$(echo "$stack" | sed '/^$/d')

        local sid="${top%% *}"
        local depth="${top##* }"

        echo "$sid $depth"
        found_any=1

        # Find parents and push onto stack (reversed for DFS order)
        local parents=""
        if [ -n "$reverse_map" ]; then
            parents=$(echo "$reverse_map" | awk -v child="$sid" '$1 == child { print $2 }')
        fi
        local new_depth=$((depth + 1))
        local reversed_parents=""
        if [ -n "$parents" ]; then
            while IFS= read -r p; do
                [ -z "$p" ] && continue
                case "$seen" in
                    *" $p "*) continue ;;
                esac
                local ppid
                ppid=$(_backend_session_exists "$p" 2>/dev/null) || true
                if [ -z "$ppid" ]; then
                    continue
                fi
                seen="$seen$p "
                reversed_parents="$p $new_depth${reversed_parents:+
$reversed_parents}"
            done <<< "$parents"
        fi
        if [ -n "$reversed_parents" ]; then
            stack="${stack:+$stack
}$reversed_parents"
        fi
    done

    [ "$found_any" -eq 1 ] && return 0 || return 1
}

# Show status of a session and all its ancestors.
# Args: session_id, mode ("oneliner" or "raw")
#
# Oneliner mode renders a tree with box-drawing characters:
#   Inner (attached, id=inner-b3a4f5e6)
#   └─ Outer (detached, id=outer-a7f3b2c1)
#
# Raw mode outputs flat key-value records in DFS order.
_session_status_ancestors() {
    local current="$1"
    local mode="${2:-oneliner}"

    local results
    results=$(_session_ancestor_walk "$current" 2>/dev/null) || true
    if [ -z "$results" ]; then
        return 0
    fi

    local raw_output
    raw_output=$(_session_list "raw")

    if [ "$mode" = "raw" ]; then
        echo "$results" | while IFS=' ' read -r sid depth; do
            echo "$raw_output" | awk -v sid="$sid" '
                /^session_id: / { current_sid = substr($0, 13) }
                current_sid == sid { print }
                current_sid == sid && /^$/ { exit }
            '
            echo ""
        done
    else
        # Use awk for the tree rendering — it handles arrays and
        # look-ahead naturally without shell word-splitting issues.
        echo "$results" | awk -v raw_output="$raw_output" '
        BEGIN {
            n = 0
            # Parse raw_output into per-session records.
            # Must iterate in order (for-in gives undefined order in awk).
            nlines = split(raw_output, raw_lines, "\n")
            cur_sid = ""
            for (i = 1; i <= nlines; i++) {
                line = raw_lines[i]
                if (line ~ /^session_id: /) cur_sid = substr(line, 13)
                if (cur_sid != "" && line ~ /^terminal_name: /) tname[cur_sid] = substr(line, 16)
                if (cur_sid != "" && line ~ /^default_name: /) dname[cur_sid] = substr(line, 15)
                if (cur_sid != "" && line ~ /^last_command: /) lcmd[cur_sid] = substr(line, 15)
                if (cur_sid != "" && line ~ /^status: /) sstatus[cur_sid] = substr(line, 9)
            }
        }
        {
            sids[n] = $1
            depths[n] = $2
            n++
        }
        END {
            for (i = 0; i < n; i++) {
                sid = sids[i]
                d = depths[i]

                # Look ahead: is there another sibling at the same depth?
                is_last = 1
                for (j = i + 1; j < n; j++) {
                    if (depths[j] == d) { is_last = 0; break }
                    if (depths[j] < d) break
                }

                # Build prefix
                prefix = ""
                if (d > 0) {
                    for (k = 1; k < d; k++) {
                        if (prev_continuing[k])
                            prefix = prefix "│  "
                        else
                            prefix = prefix "   "
                    }
                    if (is_last)
                        prefix = prefix "└─ "
                    else
                        prefix = prefix "├─ "
                }

                # Update continuing set
                if (is_last)
                    delete prev_continuing[d]
                else
                    prev_continuing[d] = 1

                # Format session info
                name = (tname[sid] != "") ? tname[sid] : dname[sid]
                line = name
                if (lcmd[sid] != "" && lcmd[sid] != name)
                    line = line " - " lcmd[sid]
                line = line " (" sstatus[sid] ", id=" sid ")"
                print prefix line
            }
        }'
    fi
}

# List ancestor session_ids for the current session (from env var).
# Used by the self-attach guard to check if a target session is an ancestor.
#
# Output: "session_id: X\npid: Y\n\n" records in DFS order.
# Exit: 0 if at least one session found, 1 otherwise.
_session_ancestors() {
    local current="${LIGHTNING_TERMINAL_SESSION_ID:-}"
    if [ -z "$current" ]; then
        return 1
    fi

    local walk
    walk=$(_session_ancestor_walk "$current") || return 1

    echo "$walk" | while IFS=' ' read -r sid depth; do
        local pid
        pid=$(_backend_session_exists "$sid" 2>/dev/null) || true
        if [ -n "$pid" ]; then
            _emit "session_id" "$sid"
            _emit "pid" "$pid"
            echo ""
        fi
    done
}

# --- Argument parsing helpers ---

# Parse common flags from args.
# Sets: _parsed_id, _parsed_name, _parsed_raw, _parsed_exec, _parsed_no_create, _parsed_rest
_parse_args() {
    _parsed_id=""
    _parsed_name=""
    _parsed_raw=""
    _parsed_exec=""
    _parsed_no_create=""
    _parsed_source=""
    _parsed_ancestors=""
    _parsed_rest=""
    while [ $# -gt 0 ]; do
        case "$1" in
            --id)        _parsed_id="${2:?--id requires a value}"; shift 2 ;;
            --name)      _parsed_name="${2:?--name requires a value}"; shift 2 ;;
            --raw)       _parsed_raw="1"; shift ;;
            --exec)      _parsed_exec="1"; shift ;;
            --no-create) _parsed_no_create="1"; shift ;;
            --ancestors) _parsed_ancestors="1"; shift ;;
            --source)
                _parsed_source="${2:?--source requires a value}"
                case "$_parsed_source" in
                    platform|user|agent|application) ;;
                    *) echo "error: --source must be one of: platform, user, agent, application" >&2; exit 1 ;;
                esac
                shift 2 ;;
            *)           _parsed_rest="${_parsed_rest:+$_parsed_rest }$1"; shift ;;
        esac
    done
}

# After _parse_args, resolve --name to a session_id if needed.
_resolve_name_to_id() {
    if [ -z "$_parsed_id" ] && [ -n "$_parsed_name" ]; then
        _parsed_id=$(_session_resolve "any_name" "$_parsed_name")
    fi
}

# Validate that only expected flags were used.
_reject_unexpected() {
    local allowed=" $1 "
    if [ -n "$_parsed_id" ]; then case "$allowed" in *" id "*) ;; *) echo "error: --id is not valid here" >&2; exit 1 ;; esac; fi
    if [ -n "$_parsed_name" ]; then case "$allowed" in *" name "*) ;; *) echo "error: --name is not valid here" >&2; exit 1 ;; esac; fi
    if [ -n "$_parsed_raw" ]; then case "$allowed" in *" raw "*) ;; *) echo "error: --raw is not valid here" >&2; exit 1 ;; esac; fi
    if [ -n "$_parsed_exec" ]; then case "$allowed" in *" exec "*) ;; *) echo "error: --exec is not valid here" >&2; exit 1 ;; esac; fi
    if [ -n "$_parsed_no_create" ]; then case "$allowed" in *" no-create "*) ;; *) echo "error: --no-create is not valid here" >&2; exit 1 ;; esac; fi
    if [ -n "$_parsed_source" ]; then case "$allowed" in *" source "*) ;; *) echo "error: --source is not valid here" >&2; exit 1 ;; esac; fi
    if [ -n "$_parsed_ancestors" ]; then case "$allowed" in *" ancestors "*) ;; *) echo "error: --ancestors is not valid here" >&2; exit 1 ;; esac; fi
    if [ -n "$_parsed_rest" ]; then case "$allowed" in *" rest "*) ;; *) echo "error: unexpected argument: $_parsed_rest" >&2; exit 1 ;; esac; fi
}

# Require --id or --name. Errors if neither is provided.
_require_id() {
    local cmd_name="$1"
    shift
    _parse_args "$@"
    _resolve_name_to_id
    if [ -z "$_parsed_id" ]; then
        echo "error: --id or --name is required for '$cmd_name'" >&2
        echo "Usage: $SCRIPT_NAME $cmd_name --id <session_id>" >&2
        exit 1
    fi
}

# Parse --id/--name with fallback to current session.
_id_or_current() {
    local cmd_name="$1"
    shift
    _parse_args "$@"
    _resolve_name_to_id
    if [ -z "$_parsed_id" ]; then
        _parsed_id="${LIGHTNING_TERMINAL_SESSION_ID:-}"
        if [ -z "$_parsed_id" ]; then
            echo "error: --id is required (not inside a session)" >&2
            echo "Usage: $SCRIPT_NAME $cmd_name [--id <session_id>]" >&2
            exit 1
        fi
    fi
}

# --- Command dispatch ---
#
# Each cmd_* function handles argument parsing and delegates to
# the appropriate _session_* function. No backend-specific code here.

cmd_ls() {
    # Usage: lightningterminal.sh ls [--raw]
    _parse_args "$@"
    _reject_unexpected "raw"
    local mode="oneliner"
    if [ "$_parsed_raw" = "1" ]; then
        mode="raw"
    fi
    _session_list "$mode"
}

cmd_new() {
    # Usage:
    #   lightningterminal.sh new                                  # anonymous session
    #   lightningterminal.sh new --name "Backend"                 # named, auto session_id
    #   lightningterminal.sh new --id "my-id"                     # specific session_id
    #   lightningterminal.sh new --name "Backend" --source agent  # with source tag
    _parse_args "$@"
    _reject_unexpected "id name source"
    _session_new "$_parsed_id" "$_parsed_name" "$_parsed_source"
}

cmd_send() {
    # Usage: lightningterminal.sh send --id|--name <..> <command...>
    _require_id "send" "$@"
    _reject_unexpected "id name rest"
    local session_id="$_parsed_id"
    local command="$_parsed_rest"
    if [ -z "$command" ]; then
        echo "error: command is required" >&2
        echo "Usage: $SCRIPT_NAME send --id <session_id> <command>" >&2
        exit 1
    fi
    _session_send "$session_id" "$command"
}

cmd_read() {
    # Usage: lightningterminal.sh read --id|--name <..>
    _require_id "read" "$@"
    _reject_unexpected "id name"
    _session_read "$_parsed_id"
}

cmd_kill() {
    # Usage: lightningterminal.sh kill [--id|--name <..>]
    # Defaults to current session if --id/--name not provided.
    _id_or_current "kill" "$@"
    _reject_unexpected "id name"
    _session_kill "$_parsed_id"
}

cmd_status() {
    # Usage: lightningterminal.sh status [--id|--name <..>] [--raw] [--ancestors]
    # Defaults to current session if --id/--name not provided.
    # With --ancestors: show the session and all its ancestors.
    _parse_args "$@"
    _resolve_name_to_id
    _reject_unexpected "id name raw ancestors"

    if [ -z "$_parsed_id" ]; then
        _parsed_id="${LIGHTNING_TERMINAL_SESSION_ID:-}"
        if [ -z "$_parsed_id" ]; then
            if [ "$_parsed_ancestors" = "1" ]; then
                return 0
            fi
            echo "error: --id is required (not inside a session)" >&2
            echo "Usage: $SCRIPT_NAME status [--id <session_id>]" >&2
            exit 1
        fi
    fi

    local mode="oneliner"
    if [ "$_parsed_raw" = "1" ]; then
        mode="raw"
    fi

    if [ "$_parsed_ancestors" = "1" ]; then
        _session_status_ancestors "$_parsed_id" "$mode"
    else
        _session_status "$_parsed_id" "$mode"
    fi
}

cmd_attach() {
    # Usage: lightningterminal.sh attach [--id <id>] [--name <n>] [--exec]
    #          [--no-create] [--source <s>]
    #
    # Attach to a session, creating it if needed.
    #   --id X        Attach to session X (create if missing, unless --no-create)
    #   --name N      Find session by name, or create with name N
    #   --exec        Replace this process (for .lightningrc)
    #   --no-create   Error if session doesn't exist (don't create)
    #   --source <s>  Source tag (platform|user|agent|application)
    #   (no args)     Create anonymous session and attach
    _parse_args "$@"
    _reject_unexpected "id name exec no-create source"
    _session_attach_or_create "$_parsed_id" "$_parsed_name" "$_parsed_exec" "$_parsed_no_create" "$_parsed_source"
}

cmd_detach() {
    # Detach from the current session.
    # Must be run from inside a session.
    _session_detach
}

cmd_last_command() {
    # Usage: lightningterminal.sh last_command --id|--name <..>
    _require_id "last_command" "$@"
    _reject_unexpected "id name"
    _session_last_command "$_parsed_id"
}

cmd_rename() {
    # Usage: lightningterminal.sh rename [--id|--name <..>] <new_name>
    # Defaults to current session if --id/--name not provided.
    _id_or_current "rename" "$@"
    _reject_unexpected "id name rest"
    local new_name="$_parsed_rest"
    if [ -z "$new_name" ]; then
        echo "error: new name is required" >&2
        echo "Usage: $SCRIPT_NAME rename [--id <session_id>] <name>" >&2
        exit 1
    fi
    _session_rename "$_parsed_id" "$new_name"
}

cmd_resolve() {
    # Resolve a target to a session_id.
    # Output: the session_id on stdout, or exit 1 if not found.
    #
    # Usage:
    #   lightningterminal.sh resolve "Backend"                    # any match
    #   lightningterminal.sh resolve --by terminal_name "Backend" # specific field
    #
    # Supported --by fields:
    #   any            Match any field (default)
    #   any_name       Match terminal_name or default_name
    #   terminal_name  Match user-given name
    #   default_name   Match system name (term-1, term-2, ...)
    #   pid            Match session PID
    #   session_id     Match session ID
    local by="any"
    if [ "${1:-}" = "--by" ]; then
        by="${2:?Usage: $SCRIPT_NAME resolve --by <field> <target>}"
        shift 2
    fi
    local target="${1:?Usage: $SCRIPT_NAME resolve [--by <field>] <target>}"
    _session_resolve "$by" "$target"
}

# --- Main ---

command="${1:-help}"
shift || true

case "$command" in
    ls)              cmd_ls "$@" ;;
    new)             cmd_new "$@" ;;
    send)            cmd_send "$@" ;;
    read)            cmd_read "$@" ;;
    kill)            cmd_kill "$@" ;;
    status)          cmd_status "$@" ;;
    attach)          cmd_attach "$@" ;;
    detach)          cmd_detach ;;
    rename)          cmd_rename "$@" ;;
    resolve)         cmd_resolve "$@" ;;
    last_command)    cmd_last_command "$@" ;;
    help|--help|-h)
        echo "Usage: $SCRIPT_NAME <command> [args]"
        echo ""
        echo "Commands:"
        echo "  ls [--raw]                            List all sessions"
        echo "  new [--id|--name <..>]  [--source X]  Create a session (detached)"
        echo "  attach [options]                      Attach to a new or existing session"
        echo "    --id <id>                           Session to attach to"
        echo "    --name <n>                          Find or create by name"
        echo "    --exec                              Replace process (for .lightningrc)"
        echo "    --no-create                         Error if session doesn't exist"
        echo "    --source <s>                        Source tag for the session"
        echo "  detach                                Detach from the current session"
        echo "  kill [--id|--name <..>]               Kill a session (default: current)"
        echo "  status [--id|--name <..>] [--raw]     Show session status (default: current)"
        echo "    --ancestors                         Include ancestor sessions (tree view)"
        echo "  send --id|--name <..> <cmd>           Send command to session"
        echo "  read --id|--name <..>                 Read session buffer"
        echo "  last_command --id|--name <..>         Last command for a session"
        echo "  rename [--id|--name <..>] <new_name>  Rename a session (default: current)"
        echo "  resolve [--by <f>] <target>           Resolve name/PID to session_id"
        echo ""
        echo "Session identification:"
        echo "  --id <session_id>   Stable programmatic identifier [a-zA-Z0-9_-]."
        echo "                      Intended for scripts and tooling."
        echo "  --name <name>       User-facing name shown in ls/status output."
        echo "                      Matches terminal name or default name (term-<N>)."
        echo "                      Names are not unique — use --id if ambiguous."
        echo "                      Sessions can be renamed with the rename command."
        echo ""
        echo "Keyboard shortcuts (inside a session):"
        echo "  Ctrl+T, D            Detach (works even when terminal is busy)"
        echo "  Ctrl+T, Ctrl+D       Detach (alternative)"
        echo "  Ctrl+T, Ctrl+T       Send literal Ctrl+T"
        echo ""
        echo "Commands marked (default: current) fall back to the current"
        echo "session if neither --id nor --name is provided."
        ;;
    *)
        echo "error: unknown command: $command" >&2
        echo "Run '$SCRIPT_NAME help' for usage." >&2
        exit 1
        ;;
esac
