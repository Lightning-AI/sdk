Sandboxes CLI examples
======================

Sandbox CLI commands use a sandbox API key. For teamspace-scoped operations,
create a teamspace API key in Lightning AI and pass it through the environment
or ``--api-key``. Do not commit API keys to source control.

Create a sandbox
----------------

.. code-block:: console

   $ pip install lightning-sdk -U
   $ export LIGHTNING_SANDBOX_API_KEY="replace-at-runtime"

   $ lightning sandbox create \
       --name sdk-tutorial-sandbox \
       --teamspace owner/teamspace \
       --instance-type cpu-1 \
       --persistent \
       --json

Run commands
------------

.. code-block:: console

   $ export SANDBOX_ID=sbx_1234567890
   $ lightning sandbox run "$SANDBOX_ID" -- python -c "print('hello from sandbox')"
   $ lightning sandbox run "$SANDBOX_ID" --cwd /workspace --env MODE=tutorial -- python app.py

Run detached and inspect logs
-----------------------------

.. code-block:: console

   $ lightning sandbox run "$SANDBOX_ID" --detached -- bash -lc "echo start; sleep 5; echo done"
   $ lightning sandbox command "$SANDBOX_ID" cmd-abc123
   $ lightning sandbox logs "$SANDBOX_ID" cmd-abc123 --no-timestamps

Stop, resume, and delete
------------------------

.. code-block:: console

   $ lightning sandbox stop "$SANDBOX_ID" --json
   $ lightning sandbox start "$SANDBOX_ID"
   $ lightning sandbox delete "$SANDBOX_ID"
