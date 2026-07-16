MMT SDK tutorial
================

MMT stands for multi-machine training. An MMT run launches the same workload
across multiple machines and tracks the group as one managed resource. Use MMT
when a training framework or distributed data job needs several workers instead
of a single node.

An MMT run has the same runtime choices as a single-machine job:

- A Studio environment, which reuses code and dependencies from a Studio.
- A Docker image, which packages the runtime independently of Studios.

The number of machines must be greater than one.

Prerequisites
-------------

Install and authenticate:

.. code-block:: console

   $ pip install lightning-sdk -U
   $ lightning login

For Studio-backed MMT runs, use an existing Studio in the target teamspace. The
SDK example fetches that Studio by name with ``create_ok=False``.

The SDK form lets Python own the launch, wait, and inspection flow:

.. literalinclude:: ../../../examples/mmts.py
   :language: python
   :start-after: # sdk-studio-mmt-start
   :end-before: # sdk-studio-mmt-end
   :dedent: 8

For a container runtime, replace ``studio=`` with ``image=``:

.. literalinclude:: ../../../examples/mmts.py
   :language: python
   :start-after: # sdk-image-mmt-start
   :end-before: # sdk-image-mmt-end
   :dedent: 8

Run the companion script directly when you want to execute the SDK example:

.. code-block:: console

   $ python python/examples/mmts.py --teamspace teamspace --org owner studio --studio sdk-tutorial-studio
   $ python python/examples/mmts.py --teamspace teamspace --org owner image

Operational notes
-----------------

- ``MMT.run`` creates a new multi-machine job; ``MMT("name", teamspace=...)``
  fetches an existing one.
- Pass ``placement_group_id=...`` when the whole MMT should join an existing
  placement group, for example to colocate with a Studio or another workload.
- ``mmt.placement_group_id`` reports the placement group associated with the
  multi-machine job, or ``None`` when the run is not tied to one.
- ``mmt.machines`` returns the per-machine job handles for detailed inspection,
  sorted by ``job.rank``.
- Each member in ``mmt.machines`` exposes the same machine-level metadata as a
  Job, including ``resource_id``, ``private_ip_address``, ``placement_group_id``,
  and ``rank``.
- ``MMT.run`` rejects ``num_machines`` values less than two.
- Studio-backed MMT runs must use a Studio in the same teamspace and cloud
  account as the run.
- The MMT object exposes high-level status and metadata; inspect the worker
  jobs when you need machine-level logs or failures.
