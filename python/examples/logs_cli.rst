Logs CLI examples
=================

Every resource that produces logs — jobs, multi-machine jobs, deployments, and
sandboxes — has its own ``logs`` command, and they share the same flags. Use
them to tail a run from a terminal, search a finished run for an error, or watch
only the lines that matter.

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

One command per resource, addressed by name (or id for sandboxes):

.. code-block:: console

   $ lightning job logs sdk-tutorial-job
   $ lightning mmt logs sdk-tutorial-mmt
   $ lightning deployment logs sdk-tutorial-api
   $ lightning sandbox logs sbx-42

A multi-machine job and a multi-replica deployment merge every machine or replica
into one timeline, and each line is labelled with where it came from. To read a
single machine of an MMT, read it as a job: ``lightning job logs <machine-name>``.

Tail and follow
---------------

``--tail`` prints the last N lines; ``--follow`` (``-f``) keeps the stream open
until the resource finishes or you press Ctrl-C:

.. code-block:: console

   $ lightning job logs sdk-tutorial-job --tail 100
   $ lightning deployment logs sdk-tutorial-api --follow
   $ lightning mmt logs sdk-tutorial-mmt --tail 50 --follow

Search and narrow
-----------------

``--query`` keeps only lines containing every whitespace-separated term,
``--severity`` sets the minimum level (``error`` > ``warning`` > ``info`` >
``debug``), and ``--since``/``--until`` bound the time range. Time bounds take a
duration — ``30s``, ``5m``, ``2h``, ``3d``, ``1w`` — or an RFC3339 timestamp:

.. code-block:: console

   $ lightning job logs sdk-tutorial-job --query "CUDA out of memory"
   $ lightning deployment logs sdk-tutorial-api --severity warning --since 2h
   $ lightning mmt logs sdk-tutorial-mmt --query error --since 3d --until 1d
   $ lightning job logs sdk-tutorial-job --since 2026-01-01T00:00:00Z

Filters combine with ``--tail`` and ``--follow``, so you can watch only what
matters, and ``--timestamps`` prefixes each line with its ISO-8601 timestamp:

.. code-block:: console

   $ lightning deployment logs sdk-tutorial-api --severity error --follow
   $ lightning job logs sdk-tutorial-job --tail 200 --timestamps

Sandboxes
---------

A sandbox reads by id, and an optional command id narrows to a single detached
command; omit it for the merged logs of every command in the sandbox:

.. code-block:: console

   $ lightning sandbox logs sbx-42
   $ lightning sandbox logs sbx-42 cmd-abc123
   $ lightning sandbox logs sbx-42 --query error

See also
--------

- ``jobs_cli.rst`` for submitting and inspecting the jobs these logs come from.
- ``sandboxes_cli.rst`` for running detached sandbox commands.
- ``lightning job logs --help`` (also ``mmt``, ``deployment``, and ``sandbox``)
  for the full option reference.
