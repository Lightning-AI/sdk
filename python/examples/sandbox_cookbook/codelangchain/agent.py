"""Build a coding agent with Lightning Sandboxes and LangGraph.

The agent is built with LangGraph: it generates Python code, then *executes
that code inside a Lightning sandbox* to check whether it actually runs, and
iterates on failures. Documentation crawled from the web informs its approach.

How the pieces fit together:
  * The LangGraph "brain" runs locally on your machine; only the agent's
    generated code runs remotely, inside a Lightning sandbox.
  * The LLM is a standard LangChain ``ChatOpenAI`` model pointed at Lightning's
    OpenAI-compatible gateway (see ``src/llm.py``). The same Lightning API key
    authenticates both the sandbox API and the LLM, so a single ``sk-lit-...``
    key is all you need -- no OpenAI/Anthropic key required.
  * The sandbox's ML dependencies (torch + transformers) are installed at
    create time (see ``src/common.py``).
  * A sandbox command's stdout and stderr arrive as one combined stream, so we
    redirect each to a separate file inside the sandbox and read them back to
    recover the (stdout, stderr) pair the graph nodes expect.

Run it from the directory that contains the ``codelangchain`` package. Provide
your Lightning API key via the environment (recommended) or --api-key:

    export LIGHTNING_SANDBOX_API_KEY=sk-lit-...
    python -m codelangchain.agent --question "How do I run a pre-trained model from the transformers library?"
"""

import argparse
import os
import time
import uuid

from lightning_sdk.sandbox import RunCommandOpts, Sandbox, SandboxInstance

from .src import edges, nodes, retrieval
from .src.common import (
    COLOR,
    SANDBOX_INSTANCE_TYPE,
    SANDBOX_RUNTIME,
    SANDBOX_SETUP_SCRIPT,
    SANDBOX_STORAGE_GB,
)

MINUTES_MS = 60 * 1000

# Environment variables checked (in order) when --api-key is not passed. The
# same Lightning key authenticates both the sandbox API and the LLM gateway.
API_KEY_ENV_VARS = ("LIGHTNING_SANDBOX_API_KEY", "LIGHTNING_API_KEY")

# Where generated code and its captured streams live inside the sandbox.
CODE_PATH = "/tmp/agent_code.py"
OUT_PATH = "/tmp/agent_stdout.txt"
ERR_PATH = "/tmp/agent_stderr.txt"

# The agent may download a model on first execution, so give each run room.
EXEC_TIMEOUT_S = 600


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
    sb: SandboxInstance,
    script: str,
    *,
    timeout: float,
    poll_interval: float = 2.0,
    stdout_path: str | None = None,
    stderr_path: str | None = None,
) -> int:
    """Run a shell ``script`` in the sandbox and block until it exits; return its exit code.

    This is the robust way to run *long* commands. A plain synchronous
    ``run_command`` has a ~120s server-side deadline (the sandbox setup and some
    code runs here take much longer), and while detached commands do run, the
    backend's command-*status* endpoints don't reliably report completion or
    output. So we launch the script detached, redirect its output to a file
    (combined, or split into ``stdout_path``/``stderr_path`` when both are
    given), and have it write an exit-code sentinel file when it finishes --
    then poll ``read_file`` (which is reliable) until that sentinel appears.
    """
    done_path = f"/tmp/.done_{uuid.uuid4().hex}"
    if stdout_path and stderr_path:
        redirect = f">{stdout_path} 2>{stderr_path}"
    else:
        redirect = f">{stdout_path}" if stdout_path else ">/dev/null 2>&1"
    # Run in a subshell so the redirect covers all of it, then record the exit
    # code the instant it finishes.
    wrapped = f"(\n{script}\n) {redirect}\necho $? >{done_path}\n"
    sb.run_command(RunCommandOpts(cmd="sh", args=["-c", wrapped], detached=True))

    deadline = time.time() + timeout
    while time.time() < deadline:
        code = sb.read_file(done_path)
        if code and code.strip():
            return int(code.strip())
        time.sleep(poll_interval)
    raise TimeoutError(f"command did not finish within {timeout}s")


def create_sandbox(timeout_ms: int = 30 * MINUTES_MS) -> SandboxInstance:
    """Create a Lightning sandbox with torch + transformers installed.

    Change this setup (and the retrieval logic in the retrieval module) if you
    want the agent to give coding advice on other libraries!
    """
    print(
        f"{COLOR['HEADER']}🏖️  Creating sandbox"
        f" ({SANDBOX_INSTANCE_TYPE}, runtime={SANDBOX_RUNTIME}){COLOR['ENDC']}"
    )

    # Sandbox.create() is not auto-retried by the SDK and can hit transient 500s.
    last_err: Exception | None = None
    sb: SandboxInstance | None = None
    for attempt in range(3):
        try:
            sb = Sandbox.create(
                name="codelangchain",
                instance_type=SANDBOX_INSTANCE_TYPE,
                runtime=SANDBOX_RUNTIME,
                storage_gb=SANDBOX_STORAGE_GB,
                timeout=timeout_ms,
            )
            break
        except RuntimeError as err:
            last_err = err
            if attempt == 2:
                raise
            print(f"{COLOR['RED']}🏖️  create failed ({err}); retrying...{COLOR['ENDC']}")
            time.sleep(2**attempt)
    assert sb is not None, last_err

    print(
        f"{COLOR['HEADER']}🏖️  Installing torch + transformers in the sandbox"
        f" (this can take a few minutes){COLOR['ENDC']}"
    )
    setup_log = "/tmp/setup.log"
    exit_code = run_and_wait(
        sb,
        SANDBOX_SETUP_SCRIPT,
        timeout=900,
        poll_interval=3.0,
        stdout_path=setup_log,
    )
    if exit_code != 0:
        log = sb.read_file(setup_log) or ""
        sb.delete()
        raise RuntimeError(
            f"sandbox dependency install failed (exit {exit_code}):\n{log}"
        )
    print(f"{COLOR['GREEN']}🏖️  Sandbox ready ({sb.sandbox_id}){COLOR['ENDC']}")
    return sb


def run(code: str, sb: SandboxInstance) -> tuple[int, str, str]:
    """Execute ``code`` inside the sandbox, returning (exit_code, stdout, stderr).

    We reuse the same sandbox container for every run, preserving state.
    Lightning merges stdout/stderr into one stream, so we redirect each to a
    file in the sandbox and read them back to recover the separate streams the
    graph nodes rely on.

    We return the process *exit code* alongside the streams: it -- not the mere
    presence of stderr -- is what distinguishes a real failure from benign
    warnings (e.g. Hugging Face writes model-download progress to stderr while
    still exiting 0).
    """
    print(
        f"{COLOR['HEADER']}📦: Running in sandbox{COLOR['ENDC']}",
        f"{COLOR['GREEN']}{code}{COLOR['ENDC']}",
        sep="\n",
    )

    sb.write_file(CODE_PATH, code)
    try:
        returncode = run_and_wait(
            sb,
            f"python -u {CODE_PATH}",
            timeout=EXEC_TIMEOUT_S,
            poll_interval=2.0,
            stdout_path=OUT_PATH,
            stderr_path=ERR_PATH,
        )
    except TimeoutError:
        returncode = 1

    stdout = sb.read_file(OUT_PATH) or ""
    stderr = sb.read_file(ERR_PATH) or ""

    if returncode != 0:
        print(
            f"{COLOR['HEADER']}📦: Failed with exitcode {returncode}{COLOR['ENDC']}"
        )

    return returncode, stdout, stderr


def construct_graph(
    sandbox: SandboxInstance,
    debug: bool = False,
    api_key: str | None = None,
):
    from langgraph.graph import StateGraph

    from .src.common import GraphState

    # Crawl the transformers documentation to inform our code generation
    context = retrieval.retrieve_docs(debug=debug)

    graph = StateGraph(GraphState)

    # Attach our nodes to the graph
    graph_nodes = nodes.Nodes(context, sandbox, run, debug=debug, api_key=api_key)
    for key, value in graph_nodes.node_map.items():
        graph.add_node(key, value)

    # Construct the graph by adding edges
    graph = edges.enrich(graph)

    # Set the starting and ending nodes of the graph
    graph.set_entry_point(key="generate")
    graph.set_finish_point(key="finish")

    return graph


DEFAULT_QUESTION = "How do I generate Python code using a pre-trained model from the transformers library?"


def go(
    question: str = DEFAULT_QUESTION,
    debug: bool = False,
    api_key: str | None = None,
) -> str:
    """Compile the Python code generation agent graph and run it, returning the result."""
    sb = create_sandbox()

    try:
        graph = construct_graph(sb, debug=debug, api_key=api_key)
        runnable = graph.compile()
        result = runnable.invoke(
            {"keys": {"question": question, "iterations": 0}},
            config={"recursion_limit": 50},
        )
    finally:
        # finish() deletes the sandbox on success; this guards every other path.
        sb.delete()

    return result["keys"]["response"]


def main(args: argparse.Namespace) -> None:
    # The same Lightning key authenticates both the sandbox API and the LLM
    # gateway -- no separate LLM provider key required.
    api_key = resolve_api_key(args.api_key)
    Sandbox.configure(api_key=api_key)

    question = args.question
    if args.debug and question == DEFAULT_QUESTION:
        question = "hi there, how are you?"

    print(go(question, debug=args.debug, api_key=api_key))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run the LangGraph coding agent in a Lightning sandbox."
    )
    parser.add_argument(
        "--question",
        default=DEFAULT_QUESTION,
        help="Question to send to the code generation agent.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Shorter context and a smaller model.",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="Lightning API key (sk-lit-...). Falls back to "
        + " / ".join(API_KEY_ENV_VARS)
        + " if unset.",
    )

    main(parser.parse_args())
