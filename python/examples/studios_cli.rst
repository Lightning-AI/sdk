Studios CLI examples
====================

Use the CLI for Studio lifecycle operations when working from a terminal,
automation script, or SSH-oriented workflow.

Create and start a Studio
-------------------------

.. code-block:: console

   $ pip install lightning-sdk -U
   $ lightning login

   $ lightning studio create \
       --name sdk-tutorial-studio \
       --teamspace owner/teamspace

   $ lightning studio start \
       --name sdk-tutorial-studio \
       --teamspace owner/teamspace \
       --machine CPU

Inspect Studios
---------------

.. code-block:: console

   $ lightning studio list --teamspace owner/teamspace --sort-by status

Connect to a Studio
-------------------

.. code-block:: console

   $ lightning studio connect sdk-tutorial-studio --teamspace owner/teamspace

Copy and list files
-------------------

.. code-block:: console

   $ lightning studio cp ./train.py lit://owner/teamspace/studios/sdk-tutorial-studio/train.py
   $ lightning studio ls lit://owner/teamspace/studios/sdk-tutorial-studio/

Stop the Studio
---------------

.. code-block:: console

   $ lightning studio stop --name sdk-tutorial-studio --teamspace owner/teamspace
