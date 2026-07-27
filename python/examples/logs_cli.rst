Logs CLI examples
=================

``lightning logs`` reads logs for anything that runs in a teamspace — jobs,
multi-machine jobs, deployments, and sandboxes — with one set of flags. Use it
to tail a run from a terminal, search a finished run for an error, or page
through a long history in a script.

Prerequisites
-------------

.. code-block:: console

   $ pip install lightning-sdk -U
   $ lightning login
   $ lightning config set teamspace owner/teamspace

Every example below also accepts ``--teamspace owner/teamspace`` explicitly; pass
it when you work across several teamspaces or run in CI.

Pick what to read
-----------------

Name or id, one resource at a time:

.. code-block:: console

   $ lightning logs --job-name sdk-tutorial-job
   $ lightning logs --job-id job-1234
   $ lightning logs --mmt-name sdk-tutorial-mmt
   $ lightning logs --deployment-name sdk-tutorial-api
   $ lightning logs --sandbox-id sbx-42

``--job-id`` can be repeated to merge several jobs into one timeline:

.. code-block:: console

   $ lightning logs --job-id job-1234 --job-id job-5678

Multi-machine jobs and multi-replica deployments are merged the same way, and
each line is labelled with the machine or replica it came from.

Tail and follow
---------------

``--tail`` prints the last N lines; ``--follow`` keeps the stream open until the
resource finishes or you press Ctrl-C:

.. code-block:: console

   $ lightning logs --job-name sdk-tutorial-job --tail 100
   $ lightning logs --deployment-name sdk-tutorial-api --follow
   $ lightning logs --mmt-name sdk-tutorial-mmt --tail 50 --follow

Search and narrow
-----------------

``--query`` matches text (matches are highlighted), ``--severity`` sets the
minimum level (``error`` > ``warning`` > ``info`` > ``debug``), and
``--since``/``--until`` bound the time range. Time bounds take a duration —
``30s``, ``5m``, ``2h``, ``3d``, ``1w`` — or an RFC3339 timestamp:

.. code-block:: console

   $ lightning logs --job-name sdk-tutorial-job --query "CUDA out of memory"
   $ lightning logs --deployment-name sdk-tutorial-api --severity warning --since 2h
   $ lightning logs --mmt-name sdk-tutorial-mmt -q error --since 3d --until 1d
   $ lightning logs --job-name sdk-tutorial-job --since 2026-01-01T00:00:00Z

Filters combine with ``--tail`` and ``--follow``, so you can watch only what
matters:

.. code-block:: console

   $ lightning logs --deployment-name sdk-tutorial-api --severity error --follow

Sandboxes
---------

A sandbox reads by id or name, and ``--sandbox-command-id`` narrows to a single
detached command:

.. code-block:: console

   $ lightning logs --sandbox-id sbx-42
   $ lightning logs --sandbox-id sbx-42 --sandbox-command-id cmd-abc123 --no-timestamps

Looking a sandbox up by ``--sandbox-name`` lists sandboxes, which needs a
teamspace- or org-scoped API key:

.. code-block:: console

   $ export LIGHTNING_SANDBOX_API_KEY="..."
   $ lightning logs --sandbox-name sdk-tutorial-sandbox --tail 20

``--sandbox-id`` works with a normal ``lightning login``.

Page through a long history
---------------------------

Without ``--tail``/``--follow``, results come back oldest-first in pages.
``--limit`` sets the page size; the command prints the next-page command on
stderr, so piping stdout stays clean:

.. code-block:: console

   $ lightning logs --job-name sdk-tutorial-job --limit 500
   $ lightning logs --job-name sdk-tutorial-job --limit 500 --page-token <token>

``--tail`` and ``--limit`` are mutually exclusive (one reads backwards from the
end, the other forwards from the start), and ``--page-token`` reads one fixed
page, so it cannot be combined with ``--follow``.

Scripting
---------

``--json`` emits entries plus the next page token, and ``--no-timestamps`` drops
the timestamp prefix for grep-friendly output:

.. code-block:: console

   $ lightning logs --job-name sdk-tutorial-job --limit 200 --json > logs.json
   $ lightning logs --job-name sdk-tutorial-job --json | jq -r '.entries[].message'
   $ lightning logs --job-name sdk-tutorial-job --no-timestamps | grep -c Traceback

Fail a CI step when a run logged an error:

.. code-block:: console

   $ lightning logs --job-name sdk-tutorial-job --severity error --limit 1 --json \
       | jq -e '.entries | length == 0'

Shortcuts
---------

``lightning job logs`` and ``lightning deployment logs`` resolve the resource for
you and print through the same reader:

.. code-block:: console

   $ lightning job logs sdk-tutorial-job --follow --timestamps
   $ lightning job logs sdk-tutorial-job --query error --severity error
   $ lightning deployment logs sdk-tutorial-api --tail 100

See also
--------

- ``jobs_cli.rst`` for submitting and inspecting the jobs these logs come from.
- ``sandboxes_cli.rst`` for running detached sandbox commands.
- ``lightning logs --help`` for the full option reference.
