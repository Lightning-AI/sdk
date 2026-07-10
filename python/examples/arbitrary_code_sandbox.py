"""Run arbitrary code in a sandboxed environment.

It demonstrates running many languages inside a single, isolated sandbox:
bash, Python, Node.js, Ruby, and PHP. It then pipes data between Python and
Node.js, streams output from a long-running process, and -- because the
sandbox is fully isolated from our machine -- runs some genuinely dangerous
code before tearing the sandbox down.

A couple of notes on how it works:

  * Lightning's curated runtimes ship *one* language each (a `python313` box
    has no `node`, a `node24` box has no `python`). So we start from `python313`
    (which already has Python + bash) and `apt-get install` the remaining
    runtimes (nodejs, ruby, php) into that same sandbox. This needs egress,
    which is on by default.

  * `sandbox.run_command(...)` runs synchronously and returns the full output
    once the process finishes -- which is all most steps here need. Synchronous
    calls have a ~120s server-side deadline, though, so for long-running work
    (the toolchain install) and for streaming a live process we launch the
    command *detached* and watch a file it writes (see `run_and_wait`).

Usage:
    # Provide your Lightning API key via the environment (recommended):
    export LIGHTNING_SANDBOX_API_KEY=sk-lit-...
    python arbitrary_code_sandbox.py

    # ...or pass it (and any other setting) explicitly:
    python arbitrary_code_sandbox.py --api-key sk-lit-... --instance-type cpu-2
"""

import argparse
import os
import time
import uuid

from lightning_sdk.sandbox import RunCommandOpts, Sandbox

# Environment variables checked (in order) when --api-key is not passed.
API_KEY_ENV_VARS = ("LIGHTNING_SANDBOX_API_KEY", "LIGHTNING_API_KEY")

MINUTES_MS = 60 * 1000


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


def run_and_wait(
    sandbox: Sandbox, script: str, *, timeout: float, poll_interval: float = 2.0
) -> tuple[int, str]:
    """Run a bash ``script`` in the sandbox and block until it exits.

    Returns ``(exit_code, combined_output)``.

    This is the robust way to run *long* commands. A plain synchronous
    ``run_command`` has a ~120s server-side deadline, so long installs fail with
    a 502; and while detached commands do run, the backend's command-*status*
    endpoints don't reliably report their completion or output. So we launch the
    script detached, redirect its combined output to a file, and have it drop an
    exit-code "sentinel" file the moment it finishes -- then poll ``read_file``
    (which is reliable) until that sentinel appears.
    """
    token = uuid.uuid4().hex
    out_path = f"/tmp/.cmd_{token}.out"
    done_path = f"/tmp/.cmd_{token}.done"
    # Run the script in a subshell so the redirect captures all of it, then
    # record the exit code in the sentinel file the instant the subshell exits.
    wrapped = f"(\n{script}\n) >{out_path} 2>&1\necho $? >{done_path}\n"
    sandbox.run_command(
        RunCommandOpts(cmd="bash", args=["-c", wrapped], detached=True)
    )

    deadline = time.time() + timeout
    while time.time() < deadline:
        exit_code = sandbox.read_file(done_path)
        if exit_code and exit_code.strip():
            return int(exit_code.strip()), (sandbox.read_file(out_path) or "")
        time.sleep(poll_interval)
    raise TimeoutError(f"command did not finish within {timeout}s")


def setup_multi_language_sandbox(args: argparse.Namespace) -> Sandbox:
    """Create a sandbox and install Node.js, Ruby and PHP alongside Python.

    Lightning runtimes ship a single language, so we start from a Python runtime
    (Python + bash already present) and apt-get install the others into the same
    box.
    """
    print(f"🏖️  Creating sandbox ({args.runtime} base)...")

    # The SDK does not auto-retry create(), and it can occasionally fail with a
    # transient 500 -- wrap it in a short backoff retry (see sandbox.md).
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            sandbox = Sandbox.create(
                name=args.name,
                instance_type=args.instance_type,
                runtime=args.runtime,
                timeout=args.timeout_ms,
            )
            break
        except RuntimeError as err:
            last_err = err
            if attempt == 2:
                raise
            print(f"🏖️  create failed ({err}); retrying...")
            time.sleep(2**attempt)
    else:  # pragma: no cover - defensive
        raise RuntimeError("unreachable") from last_err

    print(f"Sandbox ID: {sandbox.sandbox_id}")

    print("🏖️  Installing nodejs, ruby and php (this can take a minute)...")
    install_script = (
        "set -eux; "
        "export DEBIAN_FRONTEND=noninteractive; "
        "apt-get update; "
        "apt-get install -y nodejs ruby php-cli"
    )
    # The install takes longer than the synchronous deadline, so run it detached
    # and wait on its sentinel file.
    exit_code, output = run_and_wait(sandbox, install_script, timeout=600)
    if exit_code != 0:
        raise RuntimeError(
            f"toolchain install failed (exit {exit_code}):\n{output}"
        )

    return sandbox


def run_in_each_language(sandbox: Sandbox) -> None:
    """Run bash, Python, Node.js, Ruby and PHP in the sandbox.

    Each snippet is short, so we run them synchronously (one call each returns
    the full output once the process exits).
    """
    print("\n--- Running bash, Python, Node.js, Ruby and PHP ---")

    commands = [
        ("bash", ["-c", "echo 'hello from bash'"]),
        ("python", ["-c", "print('hello from python')"]),
        ("node", ["-e", 'console.log("hello from nodejs")']),
        ("ruby", ["-e", "puts 'hello from ruby'"]),
        ("php", ["-r", "echo 'hello from php';"]),
    ]

    for cmd, cmd_args in commands:
        result = sandbox.run_command(cmd, cmd_args)
        print(result.output.rstrip())


def pipe_python_into_node(sandbox: Sandbox) -> None:
    """Pipe data between Python and Node.js using bash.

    Python generates ten random numbers; Node.js reads them from stdin and
    prints their sum.
    """
    print("\n--- Piping Python -> Node.js via bash ---")

    combined = sandbox.run_command(
        "bash",
        [
            "-c",
            """python -c 'import random; print(" ".join(str(random.randint(1, 100)) for _ in range(10)))' |
            node -e 'const readline = require("readline");
            const rl = readline.createInterface({input: process.stdin});
            rl.on("line", (line) => {
              const sum = line.split(" ").map(Number).reduce((a, b) => a + b, 0);
              console.log(`The sum of the random numbers is: ${sum}`);
              rl.close();
            });'""",
        ],
    )
    print(combined.output.strip())


def stream_long_running_process(sandbox: Sandbox) -> None:
    """Stream output from a long-running process as it is produced.

    There's no stdout iterator for a running command (and the detached
    command-status endpoints don't stream output), so we launch the process
    detached with its output redirected to a file, then poll that file with
    ``read_file`` and print only the newly-appended bytes each tick. Ruby
    flushes stdout so the lines land in the file incrementally.
    """
    print("\n--- Streaming a long-running Ruby process ---")

    ruby_script = """
    10.times do |i|
      puts "Line #{i + 1}: #{Time.now}"
      STDOUT.flush
      sleep(0.5)
    end
    """
    # Write the script to a file to avoid nested shell quoting, then launch it
    # detached with output going to a file we can tail.
    sandbox.write_file("/root/slow_printer.rb", ruby_script)
    token = uuid.uuid4().hex
    out_path = f"/tmp/.stream_{token}.out"
    done_path = f"/tmp/.stream_{token}.done"
    wrapped = f"ruby /root/slow_printer.rb >{out_path} 2>&1\necho $? >{done_path}\n"
    sandbox.run_command(
        RunCommandOpts(cmd="bash", args=["-c", wrapped], detached=True)
    )

    printed = 0
    while True:
        output = sandbox.read_file(out_path) or ""
        if len(output) > printed:
            print(output[printed:], end="", flush=True)
            printed = len(output)
        if (sandbox.read_file(done_path) or "").strip():
            break
        time.sleep(0.25)


def run_dangerous_code(sandbox: Sandbox) -> None:
    """Run genuinely destructive code -- safe because the sandbox is isolated."""
    print("\n--- Running dangerous code (rm -rf / inside the sandbox) ---")
    try:
        sandbox.run_command("rm", ["-rfv", "/", "--no-preserve-root"])
    except RuntimeError as err:
        # Wiping the filesystem can knock out the in-sandbox agent mid-command;
        # that's expected here since we're about to delete the sandbox anyway.
        print(f"(sandbox stopped responding, as expected: {err})")
    print("The sandbox filesystem has been wiped.")


def main(args: argparse.Namespace) -> None:
    # The SDK reads env credentials once at import, so we configure the key
    # in-process instead (this works regardless of import order).
    Sandbox.configure(api_key=resolve_api_key(args.api_key))

    sandbox = setup_multi_language_sandbox(args)
    try:
        run_in_each_language(sandbox)
        pipe_python_into_node(sandbox)
        stream_long_running_process(sandbox)
        run_dangerous_code(sandbox)
    finally:
        # Clean up after ourselves -- remote sandboxes are not garbage-collected.
        print("\n🏖️  Terminating sandbox...")
        sandbox.delete()
        print("Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run arbitrary multi-language code in a Lightning Sandbox."
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
        default="example-safe-code-execution",
        help="Sandbox name (default: example-safe-code-execution).",
    )
    parser.add_argument(
        "--instance-type",
        default="cpu-1",
        help="Sandbox instance type (default: cpu-1).",
    )
    parser.add_argument(
        "--runtime",
        default="python313",
        help="Base sandbox runtime; must provide Python + bash (default: python313).",
    )
    parser.add_argument(
        "--timeout-ms",
        type=int,
        default=30 * MINUTES_MS,
        help="Sandbox max lifetime in ms (default: 30 min).",
    )
    main(parser.parse_args())
