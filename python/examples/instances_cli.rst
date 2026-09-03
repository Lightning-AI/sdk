Cloud instances CLI examples
============================

Cloud instances are plain VMs owned by an organization. Lightning provisions the
machine, injects the SSH keys registered on your Lightning account, and leaves
the rest to you.

Pick a machine type
-------------------

.. code-block:: console

   $ pip install lightning-sdk -U
   $ lightning login
   $ lightning ssh configure

   $ lightning instance types --org my-org
   $ lightning instance images --org my-org

Create an instance
------------------

``--port`` can be repeated and is the only way to expose ports: instances have no
update call, so recreate the instance to change the set.

.. code-block:: console

   $ lightning instance create sdk-tutorial-vm \
       --instance-type cpu-4 \
       --org my-org \
       --port 8080 \
       --volume-size 400 \
       --wait \
       --json

Boot it with a ``#cloud-config`` file, from a path or from stdin:

.. code-block:: console

   $ lightning instance create sdk-tutorial-vm -t cpu-4 --cloud-init ./cloud-init.yaml
   $ cat cloud-init.yaml | lightning instance create sdk-tutorial-vm -t cpu-4 --cloud-init -

Inspect and connect
-------------------

.. code-block:: console

   $ lightning instance list --org my-org
   $ lightning instance get sdk-tutorial-vm --org my-org --json

   $ lightning instance ssh sdk-tutorial-vm
   $ lightning instance ssh sdk-tutorial-vm -- uname -a
   $ lightning instance ssh sdk-tutorial-vm -i ~/.ssh/id_ed25519 -- uname -a
   $ lightning instance ssh sdk-tutorial-vm --print

``ssh`` exits with the remote command's exit code, so it composes with shell
scripts and CI steps.

Delete
------

Deleting an instance destroys its volume with it.

.. code-block:: console

   $ lightning instance delete sdk-tutorial-vm --org my-org --yes

Operational notes
-----------------

- ``--org`` falls back to ``LIGHTNING_ORG``, the configured default organization,
  the owner of the configured default teamspace, and finally to the only
  organization you belong to.
- ``--cloud-account`` defaults to the only cloud account able to host instances.
- Every command supports ``--json`` for scripting.
- ``--image`` and ``--cloud-init`` are part of the API contract but are rejected
  by Lightning today with ``Not supported by Lightning yet``.
