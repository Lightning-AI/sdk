MMT CLI examples
================

Use the CLI for multi-machine training when you want a scriptable distributed
launch path without writing Python orchestration code.

Prerequisites
-------------

.. code-block:: console

   $ pip install lightning-sdk -U
   $ lightning login
   $ lightning studio start --name sdk-tutorial-studio --teamspace owner/teamspace --machine CPU --create

Run a Studio-backed MMT
-----------------------

.. code-block:: console

   $ lightning mmt run \
       --name sdk-tutorial-mmt \
       --teamspace owner/teamspace \
       --studio sdk-tutorial-studio \
       --num-machines 2 \
       --machine CPU \
       --env RUN_MODE=distributed \
       --command "python train_distributed.py --epochs 1"

Inspect and list MMTs
---------------------

.. code-block:: console

   $ lightning mmt inspect sdk-tutorial-mmt --teamspace owner/teamspace
   $ lightning mmt list --teamspace owner/teamspace --sort-by status

Run an image-backed MMT
-----------------------

.. code-block:: console

   $ lightning mmt run \
       --name sdk-image-mmt \
       --teamspace owner/teamspace \
       --image pytorch/pytorch:2.4.1-cuda12.1-cudnn9-runtime \
       --num-machines 2 \
       --machine L4 \
       --command "python -m torch.distributed.run --nproc_per_node=1 train.py"

Clean up
--------

.. code-block:: console

   $ lightning mmt stop sdk-tutorial-mmt --teamspace owner/teamspace
   $ lightning mmt delete sdk-tutorial-mmt --teamspace owner/teamspace
