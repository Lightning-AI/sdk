# `lightning terminal` — Terminal Session Management

Manages persistent terminal sessions inside Lightning Studios.

## Architecture

Two CLI layers with distinct audiences, both built on the shell script:

```
Users / Interactive          Agents / Programs / Scripts
        |                               |
lightning terminal ls                   |
  (Python CLI)                          |
        |                               |
        +-------------------------------+
                       |
              lightningterminal.sh ls
                  (Shell CLI)
                       |
              screen / tmux / etc
                  (Backend)
```

### Shell CLI (`lightningterminal.sh` / `lt`)

The **programmatic interface**. Intended for agents, scripts, and system
tooling to call directly. Also accessible as `lt` (a shell function defined
in `lightningterminal.rc`).

**Output modes:**

- Default: human-readable one-liner — `Name - last_cmd (status, id=X)`
- `--raw`: structured key-value records for programmatic parsing

Most commands accept `--id <session_id>` or `--name <name>` to identify
a session. `--name` matches either the user-set `terminal_name` or the
system-generated `default_name` (`term-<N>`).

Sessions are identified by **`session_id`** — the stable programmatic reference.
Session IDs must match `[a-zA-Z0-9_-]+` (no spaces, no special characters).
When a session is created with `--name`, the session_id is derived by
sanitising the name and appending a random hex suffix (e.g. `"My Backend"`
becomes `backend-a7f3b2c1`).

Works in both bash and zsh. Creates sessions with env vars passed via `env`
so the inner shell inherits them at fork time — no race condition.

### Python CLI (`lightning terminal`) *(coming soon)*

The **user-facing interface**. Intended for humans typing at a prompt.
Refers to sessions by **name** — either the user-set `terminal_name` or the
auto-generated `default_name` (`term-<N>`). Users can also use a name
prefix, PID, or PID prefix. The `session_id` is available (e.g. in JSON
output) but isn't the primary way users refer to sessions.

Adds on top of the shell CLI:

- Rich table formatting with colour support
- JSON output mode (`--json`)
- Session name resolution (prefix matching, disambiguation)
- Sort order: current session first, then attached, then by creation date

### Naming model

| Field           | Audience | Description                                                                          |
| --------------- | -------- | ------------------------------------------------------------------------------------ |
| `session_id`    | Programs | Stable internal ID. Must match `[a-zA-Z0-9_-]+`. Not shown by default in tables.     |
| `terminal_name` | Users    | User-defined name (set at creation or via `rename`). Free-form text.                 |
| `default_name`  | Users    | System-generated fallback: `term-<N>` (auto-incrementing index).                     |
| `resolved_name` | Users    | `terminal_name` if set, otherwise `default_name`. What appears in the "Name" column. |
| `last_command`  | Both     | Last command name from lightningterminal.rc preexec hook.                            |

The key distinction: any "Name" is user-facing and can contain arbitrary text.
The `session_id` is programmatic-facing — it's what the shell CLI uses to
identify sessions, and it's constrained to safe characters (partly for
historic reasons: it's used as a screen socket name and metadata filename).

### Shell init (`lightningterminal.rc`)

Sourced by the inner shell's rc file (`.zshrc` / `.bashrc`). Installs a
preexec hook that records the last command name (not arguments) to the
history file. This is what powers the "Last Command" column in `ls`.

Only the command name is recorded (e.g. `curl`, not `curl -H 'Auth: Bearer secret'`)
to mitigate the risk of secrets leaking into the history file.

### Production code layout

```
terminal/
    README.md
    scripts/
        lightningterminal.sh         # Shell CLI
        lightningterminal.rc         # Shell init for preexec hooks
    # Coming soon:
    # __init__.py              # Re-exports terminal group from group.py
    # group.py                 # Click group definition + command registration
    # guard.py                 # @require_studio decorator
    # backend.py               # SessionBackend protocol, TerminalInfo, resolve_terminal()
    # commands/                # Python CLI commands (ls, status, ...)
```

### Metadata

Per-session files in `.terminal-meta/` alongside the screen sockets
(on tmpfs, wiped on reboot with the sockets):

```
/run/screen/S-{user}/
    {pid}.{session_id}              # screen socket
    .terminal-meta/
        {session_id}.meta           # name, created, source
        {session_id}.history        # last command (appended by preexec)
```

### Environment variables

| Variable                               | Purpose                                                       |
| -------------------------------------- | ------------------------------------------------------------- |
| `LIGHTNING_TERMINAL_STUDIO`            | `1` = force studio mode, `0` = force non-studio               |
| `LIGHTNING_TERMINAL_SCREENDIR`         | Override screen socket directory                              |
| `LIGHTNING_TERMINAL_SCREENRC`          | Override screenrc path for session creation                   |
| `LIGHTNING_TERMINAL_BACKEND`           | Backend: `screen` (default)                                   |
| `LIGHTNING_TERMINAL_SESSION_ID`        | Set by session creator, inherited by inner shell              |
| `LIGHTNING_TERMINAL_LAST_COMMAND_FILE` | History file path, inherited by inner shell                   |
| `LIGHTNING_TERMINAL_RC_PATH`           | Path to lightningterminal.rc (for test harness)               |
| `LIGHTNING_TERMINAL_HELP_SCRIPT_NAME`  | Override script name in help/error messages (e.g. `lt`)       |
| `NO_COLOR` / `FORCE_COLOR`             | Color output control per [no-color.org](https://no-color.org) |

## Testing approach

We favour **integration tests over unit tests**. The terminal commands
interact with real screen sessions, real shells, and real file systems.
Mocking these would hide the bugs that matter most — timing issues,
shell compatibility, env var propagation, buffer content.

Unit tests for pure logic (resolve algorithm, sort order) will be added
with the Python CLI layer.

### Integration test design

Tests are **behavioural** — they describe what the user/agent experiences,
not implementation details. The fact that we use screen internally is an
implementation detail; the tests should survive a switch to tmux.

Tests follow Given/When/Then:

- **Given** a studio-like setup (`given_session(name="Backend")`)
- **When** I run a command (`shell_env.run("ls")`)
- **Then** the snapshot captures the output, and inline assertions verify key properties

Every test automatically records a **narrative transcript** of all commands
and their output. This transcript is compared to a syrupy snapshot at
teardown. The snapshot shows the full story — what was set up, what commands
were run, what output was produced — making it easy to spot regressions at
a glance.

### Parametrization

- **Shell:** `shell_cli` tests run against both bash and zsh (the script must
  work in both). The inner session shell matches the script shell.
- **Backend:** all integration tests parametrize across available backends
  (currently `screen`). Adding tmux would run all tests for both automatically.
- **Color:** `python_cli` tests use a `color` fixture for display-sensitive tests. *(coming soon)*

### Running tests

```bash
# All terminal tests (from repo root or from python/tests/)
pytest python/tests/cli/terminal/ -v
cd python/tests && pytest cli/terminal/ -v

# Just shell script tests
pytest python/tests/cli/terminal/integration/shell_cli/ -v

# Just Python CLI tests (coming soon)
# pytest python/tests/cli/terminal/integration/python_cli/ -v

# Just unit tests (coming soon)
# pytest python/tests/cli/terminal/unit/ -v

# Regenerate snapshots after intentional output changes
pytest python/tests/cli/terminal/ --snapshot-update

# Run in parallel (requires pytest-xdist)
# --dist loadfile groups tests by file so snapshot writes don't conflict
pytest python/tests/cli/terminal/ -n auto --dist loadfile
```

### Detecting PTY leaks

Each screen session holds a PTY pair. If test teardown fails to kill sessions,
PTYs accumulate and eventually exhaust the kernel limit (`/proc/sys/kernel/pty/max`),
causing all session creation to silently fail.

To check for leaks, compare PTY count before and after a test run:

```bash
echo "before: $(ls /dev/pts/ | wc -l)"
pytest python/tests/cli/terminal/ -v
echo "after: $(ls /dev/pts/ | wc -l)"
```

The counts should match. If they don't, check for orphaned screen processes:

```bash
ps aux | grep "SCREEN.*-dmS" | grep -v "claude\|setup"
```

The test fixtures guard against this with:

- `try/finally` ensuring teardown runs even when assertions fail
- PID tracking to kill sessions directly (fallback for `screen -X quit`)
- Case-insensitive parsing of `screen -ls` output (screen 5 with multiuser
  shows `(Multi, detached)` not `(Detached)`)
