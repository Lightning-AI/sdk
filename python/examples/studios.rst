Studios SDK tutorial
====================

A Studio is a persistent Lightning AI development environment. Use a Studio for
interactive work, dependency setup, exploratory runs, and as a reusable runtime
for jobs or MMT runs. Starting a Studio attaches compute. Stopping a Studio
releases compute while preserving the Studio resource.

Prerequisites
-------------

Install and authenticate:

.. code-block:: console

   $ pip install lightning-sdk -U
   $ lightning login

The SDK gives you a Python object that can start compute, execute commands, and
transfer files. The executable script stops the Studio after any optional
commands complete:

.. literalinclude:: ../../../examples/studios.py
   :language: python
   :start-after: # sdk-studio-workflow-start
   :end-before: # sdk-studio-workflow-end
   :dedent: 4

Use ``run_with_exit_code`` when failure is part of the control flow and you do
not want a non-zero command to raise immediately. The companion script runs this
branch only when ``--run-tests`` is passed:

.. literalinclude:: ../../../examples/studios.py
   :language: python
   :start-after: # sdk-studio-exit-code-start
   :end-before: # sdk-studio-exit-code-end
   :dedent: 4

Use ``run_and_detach`` for background work where you only need early output and
the command should continue in the Studio. The companion script runs this branch
only when ``--detach-training`` is passed:

.. literalinclude:: ../../../examples/studios.py
   :language: python
   :start-after: # sdk-studio-detach-start
   :end-before: # sdk-studio-detach-end
   :dedent: 4

Run the companion script directly when you want to execute the SDK example:

.. code-block:: console

   $ python python/examples/studios.py --teamspace teamspace --org owner --studio sdk-tutorial-studio
   $ python python/examples/studios.py --teamspace teamspace --org owner --studio sdk-tutorial-studio --run-tests

Operational notes
-----------------

- ``Studio("name", teamspace=..., create_ok=True)`` creates the Studio when it
  does not exist. Use ``create_ok=False`` when automation should fail instead of
  creating a new resource.
- ``studio.start`` is blocking while compute is provisioned.
- ``studio.placement_group_id`` reports the active Studio compute placement
  group, or ``None`` when placement metadata is not available. Use this value as
  ``placement_group_id=...`` for Jobs or MMTs that must colocate with the
  Studio.
- ``studio.run`` requires the Studio to be running and raises if the command
  exits non-zero.
- Jobs and MMTs can reuse a Studio environment, which is useful when the Studio
  contains dependencies, code, or secrets configured through Lightning.
- Stop Studios when you do not need active compute.
