"""Build a stateful, sandboxed code interpreter on a Lightning Sandbox.

It runs a long-lived Python "driver program" inside the sandbox that:

  * listens for code sent on its standard input (`stdin`),
  * `exec`s that code against a *persistent* ``globals`` dict (so the
    interpreter is stateful across calls), and
  * returns the captured ``stdout`` / ``stderr`` as JSON on its standard
    output (`stdout`).

Because we're inside a sandbox, using the "unsafe" ``exec()`` is fine.

To talk to that long-lived program we need a live, bidirectional connection.
``sandbox.run_command`` is request/response with no persistent stdin, so we use
a **PTY session** (``sandbox.process.create_pty``) instead. A PTY echoes input
and merges stdout/stderr into one stream, so the driver wraps every reply in
unique sentinel markers that we parse out of the terminal byte stream.

One more PTY quirk we work around: the interactive-input transport silently
drops lines containing double quotes (``"``), so we cannot feed raw JSON in on
``stdin``. Instead we base64-encode the code (URL-safe alphabet, no quotes) on
the way in; the driver decodes it. The reply on the way out is plain JSON,
which is unaffected.

Usage:
    # Provide your Lightning API key via the environment (recommended):
    export LIGHTNING_SANDBOX_API_KEY=sk-lit-...
    python interpreter_sandbox.py

    # ...or pass it (and any other setting) explicitly:
    python interpreter_sandbox.py --api-key sk-lit-... --instance-type cpu-2
"""

import argparse
import base64
import inspect
import json
import os
import sys
import time

from lightning_sdk.sandbox import PtyCreateOpts, Sandbox

# Environment variables checked (in order) when --api-key is not passed.
API_KEY_ENV_VARS = ("LIGHTNING_SANDBOX_API_KEY", "LIGHTNING_API_KEY")

# Sentinel markers the driver wraps each JSON reply in. A PTY echoes our input
# and mixes stdout+stderr into one stream, so we can't assume "one JSON object
# per line". Instead the driver brackets each reply with these unlikely tokens
# and we slice them out of the accumulated terminal output.
#
# Use *printable* tokens, not ASCII control bytes: writing e.g. \x05 (ENQ) to a
# terminal triggers "answerback" and quietly breaks the line discipline, so the
# driver would stop receiving our stdin entirely.
RESULT_START = "<<<<<INTERP_RESULT_8f3a2b1c>>>>>"
RESULT_END = "<<<<<INTERP_END_8f3a2b1c>>>>>"
# Printed once on stderr when the driver is up and listening for commands.
READY_MARKER = "<<<<<INTERP_READY_8f3a2b1c>>>>>"


def driver_program():
    import base64
    import json
    import sys
    from contextlib import redirect_stderr, redirect_stdout
    from io import StringIO

    # Sentinels must match the client side (kept inline so this function is
    # self-contained when shipped into the sandbox via inspect.getsource).
    RESULT_START = "<<<<<INTERP_RESULT_8f3a2b1c>>>>>"
    RESULT_END = "<<<<<INTERP_END_8f3a2b1c>>>>>"
    READY_MARKER = "<<<<<INTERP_READY_8f3a2b1c>>>>>"

    # When you `exec` code in Python, you can pass in a dictionary that defines
    # the global variables the code has access to. We reuse one dict for the
    # whole session, which is what makes the interpreter stateful.
    session_globals: dict = {}

    sys.stderr.write(READY_MARKER + "\n")
    sys.stderr.flush()

    while True:
        line = sys.stdin.readline()
        if not line:  # stdin closed -> shut the driver down
            break
        line = line.strip()
        if not line:
            continue

        # Each command line is URL-safe base64 of the code to run (raw JSON on
        # stdin is unreliable through the PTY, which drops double quotes).
        try:
            code = base64.urlsafe_b64decode(line.encode()).decode()
        except Exception:
            continue  # ignore terminal echo / malformed noise

        # Capture the executed code's outputs.
        stdout_io, stderr_io = StringIO(), StringIO()
        with redirect_stdout(stdout_io), redirect_stderr(stderr_io):
            try:
                exec(code, session_globals)
            except Exception as e:
                print(f"Execution Error: {e}", file=sys.stderr)
        result = {
            "stdout": stdout_io.getvalue(),
            "stderr": stderr_io.getvalue(),
        }

        sys.stdout.write(RESULT_START + json.dumps(result) + RESULT_END)
        sys.stdout.flush()


class SandboxInterpreter:
    """A stateful code interpreter backed by a Lightning Sandbox PTY session."""

    def __init__(self, sandbox: Sandbox):
        self.sandbox = sandbox
        self._buf = bytearray()
        self._consumed = 0  # how many complete result blocks we've returned
        self.pty = None

    def start(self) -> None:
        # Ship the driver into the sandbox. We convert the function to source
        # with inspect.getsource and append a call so running the file boots the
        # interpreter loop.
        driver_text = inspect.getsource(driver_program)
        driver_command = f"{driver_text}\n\ndriver_program()\n"
        self.sandbox.write_file("/root/driver.py", driver_command)

        # Open a live PTY and accumulate everything it emits into a buffer.
        self.pty = self.sandbox.process.create_pty(
            PtyCreateOpts(
                session_name="interpreter",
                cwd="/root",
                cols=200,
                rows=50,
                on_data=lambda chunk: self._buf.extend(chunk),
            )
        )
        self.pty.wait_for_connection(timeout=30)

        # `-u` keeps stdout/stderr unbuffered so replies arrive live. The driver
        # turns the interactive shell into a clean JSON request/response pipe.
        self.pty.send_input("python3 -u /root/driver.py\n")
        self._wait_for(READY_MARKER, timeout=30)

    def _wait_for(self, marker: str, timeout: float) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if marker in self._buf.decode(errors="replace"):
                return
            time.sleep(0.1)
        raise TimeoutError(f"Timed out waiting for driver (looking for marker).")

    def _next_result(self, timeout: float) -> dict:
        """Block until the next complete result block is available, then parse it."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            text = self._buf.decode(errors="replace")
            blocks = []
            search_from = 0
            while True:
                start = text.find(RESULT_START, search_from)
                if start == -1:
                    break
                end = text.find(RESULT_END, start)
                if end == -1:
                    break  # reply still streaming in
                payload = text[start + len(RESULT_START):end]
                blocks.append(payload)
                search_from = end + len(RESULT_END)

            if len(blocks) > self._consumed:
                payload = blocks[self._consumed]
                self._consumed += 1
                return json.loads(payload)
            time.sleep(0.05)
        raise TimeoutError("Timed out waiting for code execution result.")

    def run_code(self, code: str, timeout: float = 30.0) -> dict:
        """Send a snippet to the interpreter, print its output, return the result."""
        payload = base64.urlsafe_b64encode(code.encode()).decode()
        self.pty.send_input(payload + "\n")
        result = self._next_result(timeout)

        print(result.get("stdout", ""), end="")
        if result.get("stderr"):
            # stderr in red.
            print(
                "\033[91m" + result["stderr"] + "\033[0m",
                end="",
                file=sys.stderr,
            )
        return result

    def close(self) -> None:
        if self.pty is not None:
            try:
                self.pty.kill()
            except Exception:
                pass


def resolve_api_key(cli_value: str | None) -> str:
    """Return the Lightning API key from --api-key or the environment.

    Precedence: the explicit ``--api-key`` flag wins; otherwise we fall back to
    the ``LIGHTNING_SANDBOX_API_KEY`` / ``LIGHTNING_API_KEY`` environment
    variables. We never hard-code a key so the example is safe to share.
    """
    if cli_value:
        return cli_value
    for env_var in API_KEY_ENV_VARS:
        value = os.environ.get(env_var)
        if value:
            return value
    raise SystemExit(
        "No Lightning API key found. Pass --api-key sk-lit-... or set one of: "
        + ", ".join(API_KEY_ENV_VARS)
    )


def main(args: argparse.Namespace) -> None:
    Sandbox.configure(api_key=resolve_api_key(args.api_key))

    print(f"Creating sandbox {args.name!r} ({args.instance_type}, {args.runtime})")
    sandbox = create_sandbox(
        args.name, args.instance_type, args.runtime, args.timeout_ms
    )

    interpreter = SandboxInterpreter(sandbox)
    try:
        print(f"Sandbox {sandbox.sandbox_id} is running; starting interpreter")
        interpreter.start()
        print("Interpreter ready.\n")

        # Now we can execute some code in the Sandbox!
        print("--- hello, world ---")
        interpreter.run_code("print('hello, world!')")  # hello, world!

        # The Sandbox and our code interpreter are stateful, so we can define
        # variables and use them in subsequent code.
        print("\n--- stateful variables ---")
        interpreter.run_code("x = 10")
        interpreter.run_code("y = 5")
        interpreter.run_code("result = x + y")
        interpreter.run_code(
            "print(f'The result is: {result}')"
        )  # The result is: 15

        # We can also see errors when code fails.
        print("\n--- error handling ---")
        interpreter.run_code("print('Attempting to divide by zero...')")
        interpreter.run_code("1 / 0")  # Execution Error: division by zero

        print("\nDone.")
    finally:
        # Finally, let's clean up after ourselves and terminate the Sandbox.
        interpreter.close()
        print(f"\nTerminating sandbox {sandbox.sandbox_id}")
        sandbox.delete()


def create_sandbox(
    name: str, instance_type: str, runtime: str, timeout_ms: int
) -> Sandbox:
    """Create a Python sandbox, retrying transient 500s (create is not auto-retried).

    ``runtime`` must be a Python runtime (the driver launches ``python3``).
    """
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            return Sandbox.create(
                name=name,
                instance_type=instance_type,
                runtime=runtime,
                timeout=timeout_ms,
            )
        except RuntimeError as err:
            last_err = err
            if attempt == 2:
                raise
            print(f"create failed ({err}); retrying...")
            time.sleep(2**attempt)
    raise RuntimeError("unreachable") from last_err


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Stateful code interpreter in a Lightning Sandbox"
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="Lightning API key (sk-lit-...). Falls back to "
        + " / ".join(API_KEY_ENV_VARS)
        + " if unset.",
    )
    parser.add_argument(
        "--name",
        default="code-interpreter",
        help="Sandbox name (default: code-interpreter).",
    )
    parser.add_argument(
        "--instance-type",
        default="cpu-1",
        help="Sandbox instance type (default: cpu-1).",
    )
    parser.add_argument(
        "--runtime",
        default="python313",
        help="Sandbox Python runtime (default: python313).",
    )
    parser.add_argument(
        "--timeout-ms",
        type=int,
        default=30 * 60 * 1000,
        help="Sandbox max lifetime in ms (default: 30 min).",
    )
    main(parser.parse_args())
