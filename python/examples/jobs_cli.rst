Jobs CLI examples
=================

Use the CLI when you want to launch, inspect, and clean up jobs from a terminal,
shell script, or CI system.

Prerequisites
-------------

.. code-block:: console

   $ pip install lightning-sdk -U
   $ lightning login
   $ lightning config set teamspace owner/teamspace
   $ lightning studio start --name sdk-tutorial-studio --teamspace owner/teamspace --machine CPU --create

Run a Studio-backed job
-----------------------

.. code-block:: console

   $ lightning job run \
       --name sdk-tutorial-job \
       --teamspace owner/teamspace \
       --studio sdk-tutorial-studio \
       --machine CPU \
       --env RUN_MODE=tutorial \
       --command "python train.py --epochs 1"

Inspect and list jobs
---------------------

.. code-block:: console

   $ lightning job inspect sdk-tutorial-job --teamspace owner/teamspace
   $ lightning job list --teamspace owner/teamspace --sort-by status

Run an image-backed job
-----------------------

.. code-block:: console

   $ lightning job run \
       --name sdk-image-job \
       --teamspace owner/teamspace \
       --image python:3.11-slim \
       --machine CPU \
       --command "python -c 'print(\"hello from a Lightning job\")'"

Clean up
--------

.. code-block:: console

   $ lightning job stop sdk-tutorial-job --teamspace owner/teamspace
   $ lightning job delete sdk-tutorial-job --teamspace owner/teamspace
