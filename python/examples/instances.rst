Cloud instances SDK tutorial
============================

A cloud instance is a plain virtual machine. Lightning provisions it, injects the
SSH keys of your Lightning account, and gets out of the way: there is no Studio,
job runtime, or agent on top of it. Use instances when you want raw compute you
administer yourself, and Studios or jobs when you want a managed environment.

Instances belong to an organization rather than a teamspace, and they are not
persistent: deleting one destroys its volume with it.

Prerequisites
-------------

Install the package, sign in, and make sure your account has an SSH key
(``lightning ssh configure`` downloads and registers one):

.. code-block:: console

   $ pip install lightning-sdk -U
   $ lightning login
   $ lightning ssh configure

Create an instance, wait for it to become reachable, run a command on it over
SSH, and delete it:

.. literalinclude:: ../../../examples/instances.py
   :language: python
   :start-after: # sdk-instance-create-start
   :end-before: # sdk-instance-create-end
   :dedent: 8

List the machine types an organization can provision, and the instances it
already runs:

.. literalinclude:: ../../../examples/instances.py
   :language: python
   :start-after: # sdk-instance-inspect-start
   :end-before: # sdk-instance-inspect-end
   :dedent: 8

Run the companion script directly when you want to execute the SDK example:

.. code-block:: console

   $ python python/examples/instances.py --org my-org create
   $ python python/examples/instances.py --org my-org inspect

Operational notes
-----------------

- ``org`` is resolved from ``LIGHTNING_ORG``, the configured default
  organization, the configured default teamspace's owner, and finally from the
  only organization you belong to.
- ``cloud_account`` defaults to the only cloud account able to host instances.
- ``wait=True`` blocks until the instance reports an SSH endpoint, so
  ``ssh_command`` is usable as soon as ``create`` returns.
- ``ssh`` uses the Lightning-managed key by default; pass ``key_path`` (``-i`` on
  the CLI) to authenticate with a different one.
- ``ports`` are fixed at creation time. Instances have no update call, so
  recreate the instance to expose a different set of ports.
- ``image`` and ``cloud_init`` are part of the API contract but are rejected by
  Lightning today; both raise ``Not supported by Lightning yet``.
