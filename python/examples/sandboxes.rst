Sandboxes SDK tutorial
======================

A sandbox is a lightweight, programmable execution environment for commands,
files, and short-lived runtime state. Use sandboxes for isolated code execution,
tool calls, temporary build steps, and workloads that do not need a full
persistent Studio.

Sandboxes use a sandbox API key. For teamspace-scoped operations, create a
teamspace API key in Lightning AI and provide it through the environment or the
SDK client configuration. Do not commit API keys to source control.

Prerequisites
-------------

Install the package and configure a sandbox API key:

.. code-block:: console

   $ pip install lightning-sdk -U
   $ export LIGHTNING_SANDBOX_API_KEY="replace-at-runtime"

The SDK exposes a client and a sandbox instance handle. Create the sandbox,
write a file, run commands, and stop it from Python:

.. literalinclude:: ../../../examples/sandboxes.py
   :language: python
   :start-after: # sdk-sandbox-create-start
   :end-before: # sdk-sandbox-create-end
   :dedent: 8

Use the client object when you need to list, fetch, resume, or delete sandboxes
from reusable application code:

.. literalinclude:: ../../../examples/sandboxes.py
   :language: python
   :start-after: # sdk-sandbox-client-start
   :end-before: # sdk-sandbox-client-end
   :dedent: 8

Run the companion script directly when you want to execute the SDK example:

.. code-block:: console

   $ python python/examples/sandboxes.py --teamspace owner/teamspace create
   $ python python/examples/sandboxes.py --teamspace owner/teamspace inspect --sandbox-id sbx_1234567890

Operational notes
-----------------

- ``Sandbox.create`` returns a running ``SandboxInstance``.
- ``persistent=True`` lets ``stop`` capture an automatic snapshot that can be
  resumed later.
- ``delete`` destroys the sandbox and discards auto-snapshot state.
- ``run_command`` accepts either a command string plus args or a
  ``RunCommandOpts`` object for cwd, environment, detached execution, and other
  command settings.
