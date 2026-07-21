###############
Lightning SDK
###############

The Lightning SDK lets you programmatically interact with `Lightning AI Studios <https://lightning.ai>`_:
run jobs, manage teamspaces, attach machines, deploy models, and more — all from Python or the CLI.

Start Here
==========

Use this path if you are new to the Lightning SDK:

1. :doc:`install`
2. :doc:`quickstart`

Key Concepts
============

- Manage :class:`~lightning_sdk.Studio` instances — create, start, stop, and run commands
- Submit and track jobs with :meth:`lightning_sdk.Job.run` and :class:`~lightning_sdk.Machine` selection
- Organize work inside a :class:`~lightning_sdk.Teamspace`
- Scale training with :meth:`lightning_sdk.MMT.run`
- Deploy models with :class:`~lightning_sdk.Deployment`

Quick Example
=============

.. code-block:: python

    from lightning_sdk import Studio, Machine

    studio = Studio("my-studio")
    studio.start()

    job = studio.run("python train.py", machine=Machine.A10G)
    job.wait()

    studio.stop()

Documentation Map
=================

:ref:`Install <install:Installation>` — set up the package and authenticate.

:ref:`Quickstart <quickstart:Quickstart>` — run your first job in minutes.

The :ref:`Examples <examples:Examples>` provide tutorial walkthroughs for
common CLI and SDK workflows.

The :ref:`API reference <api:API Reference>` documents every public class and function.

.. _start-section:

Start
=====

.. toctree::
    :maxdepth: 1

    install
    quickstart
    examples
    api
