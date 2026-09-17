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

Whatever a job writes to disk is kept in the teamspace drive under
``jobs/<job name>``, and stays there until the job is deleted. Read it from
anywhere with the teamspace's download methods:

.. literalinclude:: ../../../examples/jobs.py
   :language: python
   :start-after: # sdk-job-artifacts-start
   :end-before: # sdk-job-artifacts-end
   :dedent: 8

Use ``download_file`` instead when you only want one file, for example
``teamspace.download_file(f"jobs/{job.name}/checkpoints/last.ckpt", "last.ckpt")``.

The same location is ``lit://<owner>/<teamspace>/jobs/<job name>`` from the CLI,
which is the quickest way to see what a job produced before downloading any of
it:

.. code-block:: console

   $ lightning ls lit://owner/teamspace/jobs/my-job
   $ lightning ls -r lit://owner/teamspace/jobs/my-job
   $ lightning cp lit://owner/teamspace/jobs/my-job/metrics.json .

It is also what the Lightning web UI shows under the job, and ``job.artifacts_uri``
returns it ready to paste.

For a multi-machine job, each machine writes its own folder. Iterate over
``mmt.machines`` and use each machine's name:

.. code-block:: python

   for machine in mmt.machines:
       teamspace.download_folder(f"jobs/{machine.name}", f"./artifacts/{machine.name}")

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
- A job's files sit directly under ``jobs/<job name>``. A Studio in the same
  teamspace mounts them one folder deeper, at
  ``/teamspace/jobs/<job name>/artifacts``, so paths copied out of a Studio do
  not address the drive.
- Studio-backed jobs must run in the same teamspace and cloud account as the
  Studio.
- Container-backed jobs cannot also pass ``studio=``.
- ``stop_on_timeout=True`` is useful for automation because it avoids leaving a
  long-running job behind when a wait loop times out.
