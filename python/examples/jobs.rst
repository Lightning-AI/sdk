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

Run the companion script directly when you want to execute the SDK example:

.. code-block:: console

   $ python python/examples/jobs.py --teamspace teamspace --org owner studio --studio sdk-tutorial-studio
   $ python python/examples/jobs.py --teamspace teamspace --org owner image

Operational notes
-----------------

- ``Job.run`` creates a new job; ``Job("name", teamspace=...)`` fetches an
  existing one.
- Pass ``placement_group_id=...`` when a job must join an existing placement
  group, for example to colocate with a running Studio, Job, or MMT.
- ``job.resource_id`` is the stable Lightning resource ID for the job.
- ``job.private_ip_address`` is populated when the job has a private worker
  address available.
- ``job.placement_group_id`` reports the placement group associated with the
  job, or ``None`` when the job is not tied to one.
- ``job.logs`` is available after the job reaches a terminal state.
- Studio-backed jobs must run in the same teamspace and cloud account as the
  Studio.
- Container-backed jobs cannot also pass ``studio=``.
- ``stop_on_timeout=True`` is useful for automation because it avoids leaving a
  long-running job behind when a wait loop times out.
