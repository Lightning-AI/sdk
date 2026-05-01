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

Stop the Studio
===============

.. code-block:: python

    studio.stop()

Next Steps
==========

- See the :doc:`api` for the full public API.
- Explore multi-machine training with :class:`~lightning_sdk.MMT`.
- Deploy a model with :class:`~lightning_sdk.Deployment`.
