Teamspaces CLI examples
=======================

The CLI does not expose a standalone ``lightning teamspace`` command group in
this package. Use ``lightning config`` to set local defaults, and use
``--teamspace owner/teamspace`` on resource commands when scripts should be
explicit about their target account.

Set and inspect context
-----------------------

.. code-block:: console

   $ pip install lightning-sdk -U
   $ lightning login
   $ lightning config set teamspace owner/teamspace
   $ lightning config show

Use explicit teamspace flags
----------------------------

.. code-block:: console

   $ lightning studio list --teamspace owner/teamspace
   $ lightning job list --teamspace owner/teamspace --sort-by status
   $ lightning mmt list --teamspace owner/teamspace --sort-by status
   $ lightning sandbox list --teamspace owner/teamspace

Set related defaults
--------------------

.. code-block:: console

   $ lightning config set org owner
   $ lightning config set studio sdk-tutorial-studio
   $ lightning config set cloud-account cloud-account-name

Prefer explicit ``--teamspace`` in CI, release scripts, and other automation so
logs show the resource scope directly.
