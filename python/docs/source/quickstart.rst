##########
Quickstart
##########

This guide shows how to start a Studio, run a job, and stop it.

Start a Studio
==============

.. code-block:: python

    from lightning_sdk import Studio

    studio = Studio("my-studio")
    studio.start()

Run a command
=============

Use :meth:`~lightning_sdk.Studio.run` to execute a shell command inside the Studio:

.. code-block:: python

    result = studio.run("echo 'Hello from Lightning!'")
    print(result)

Run a job on a GPU machine
==========================

Pass a :class:`~lightning_sdk.Machine` to run on accelerated hardware:

.. code-block:: python

    from lightning_sdk import Studio, Machine

    studio = Studio("my-studio")
    job = studio.run("python train.py", machine=Machine.A10G)
    job.wait()

Submit a named job
==================

Use :meth:`lightning_sdk.Job.run` when you want to submit a named async job directly:

.. code-block:: python

    from lightning_sdk import Job, Machine

    job = Job.run(
        name="train-model",
        command="python train.py",
        machine=Machine.A10G,
        studio="my-studio",
    )
    job.wait()

Submit multi-machine training
=============================

Use :meth:`lightning_sdk.MMT.run` for distributed training across multiple machines:

.. code-block:: python

    from lightning_sdk import MMT, Machine

    mmt = MMT.run(
        name="distributed-train",
        command="python train.py",
        num_machines=4,
        machine=Machine.A10G,
        studio="my-studio",
    )
    mmt.wait()

Stop the Studio
===============

.. code-block:: python

    studio.stop()

Next Steps
==========

- See the :doc:`api` for the full public API.
- Explore multi-machine training with :meth:`lightning_sdk.MMT.run`.
- Deploy a model with :class:`~lightning_sdk.Deployment`.
