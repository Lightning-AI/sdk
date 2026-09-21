Jobs SDK tutorial
=================

Jobs run a command on managed compute and then exit. Use a job when you want a
repeatable batch task: training, evaluation, data preparation, or a scheduled
script. A job belongs to a teamspace, runs on a selected machine type, and uses
either a Studio environment or a Docker image as its runtime.

There are two common launch styles:

- Use ``--studio`` or ``studio=...`` when the code and dependencies already live
  in a Lightning Studio.
- Use ``--image`` or ``image=...`` when the runtime is packaged as a container.

Jobs are named within a teamspace. Pick stable names for automation so later
commands can inspect, stop, or delete the exact run.

Prerequisites
-------------

Install and authenticate:

.. code-block:: console

   $ pip install lightning-sdk -U
   $ lightning login

Choose a teamspace. For Studio-backed jobs, use an existing Studio in that
teamspace. The SDK example fetches that Studio by name with ``create_ok=False``
so automation fails instead of silently creating the wrong runtime.

The SDK form is better when the job is part of Python application logic. The
same Studio-backed job can be expressed with objects, waited on, and inspected:

.. literalinclude:: ../../../examples/jobs.py
   :language: python
   :start-after: # sdk-studio-job-start
   :end-before: # sdk-studio-job-end
   :dedent: 8

The same pattern works for containers. Use ``image=`` instead of ``studio=`` and
pass container-specific options only when you need them:

.. literalinclude:: ../../../examples/jobs.py
   :language: python
   :start-after: # sdk-image-job-start
   :end-before: # sdk-image-job-end
   :dedent: 8

Reading a job's artifacts
-------------------------

Whatever a job writes to disk is kept in the teamspace drive, and stays there
until the job is deleted. The job object reads it from anywhere:

.. literalinclude:: ../../../examples/jobs.py
   :language: python
   :start-after: # sdk-job-artifacts-start
   :end-before: # sdk-job-artifacts-end
   :dedent: 8

``list_artifacts`` returns one entry per file or folder, with its ``path``,
``size`` and ``last_modified``. Both it and ``download_artifacts`` take a
``path`` to work on one subfolder, so a long training run does not have to come
down whole::

   job.download_artifacts("./checkpoints", path="checkpoints")

``job.artifacts_uri`` is the same location as a ``lit://`` address, which is
what the CLI takes and what the Lightning web UI shows under the job:

.. code-block:: console

   $ lightning ls lit://owner/teamspace/jobs/my-job
   $ lightning ls -r lit://owner/teamspace/jobs/my-job
   $ lightning cp lit://owner/teamspace/jobs/my-job/metrics.json .

A multi-machine job has no single artifact folder, because every machine writes
its own. ``mmt.download_artifacts`` handles that: it gives each machine a
folder named after it, and ``mmt.list_artifacts`` prefixes each path the same
way, so the listing and the download agree.

Run the companion script directly when you want to execute the SDK example:

.. code-block:: console

   $ python python/examples/jobs.py --teamspace teamspace --org owner studio --studio sdk-tutorial-studio
   $ python python/examples/jobs.py --teamspace teamspace --org owner image
   $ python python/examples/jobs.py --teamspace teamspace --org owner artifacts --name sdk-tutorial-job

Operational notes
-----------------

- ``Job.run`` creates a new job; ``Job("name", teamspace=...)`` fetches an
  existing one.
- ``job.logs`` reads the logs saved so far, whether the job is running or
  finished. Call it to pass options: ``job.logs(follow=True)`` streams new lines
  from a running job, and ``tail``, ``timestamps``, ``query`` (only lines
  containing every whitespace-separated term) and ``severity`` (``error``,
  ``warning``, ``info`` or ``debug`` and above) narrow what comes back.
- ``mmt.logs`` reads every machine of a multi-machine job, merged into one
  timeline and labelled with the machine each line came from.
- The same reads are available from the CLI, one command per resource:
  ``lightning job logs <name>``, ``lightning mmt logs <name>``,
  ``lightning deployment logs <name>`` and ``lightning sandbox logs <id>``. Each
  takes ``--follow``, ``--tail``, ``--since``/``--until``, ``--query`` and
  ``--severity``.
- A container job only keeps artifacts when it was launched with
  ``artifacts_destination``. Without it ``job.artifacts_uri`` is ``None``,
  ``list_artifacts`` is empty, and ``download_artifacts`` raises.
- A job's files sit directly under ``jobs/<job name>`` in the drive. A Studio in
  the same teamspace mounts them one folder deeper, at
  ``/teamspace/jobs/<job name>/artifacts``, so a path copied out of a Studio
  does not address the drive.
- Studio-backed jobs must run in the same teamspace and cloud account as the
  Studio.
- Container-backed jobs cannot also pass ``studio=``.
- ``stop_on_timeout=True`` is useful for automation because it avoids leaving a
  long-running job behind when a wait loop times out.
