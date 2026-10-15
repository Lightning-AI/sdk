VM network groups
=================

``VMNetworkGroup`` connects existing native VMs in one organization, teamspace,
and machine cluster through advertised private node addresses. Creation and
adding members require the per-user ``VMNetworkGroups`` feature flag and compatible
baremetal agents with routed in-band address pools. This interface is experimental
and requires the corresponding control-plane feature to be deployed.

Add a node
----------

Resolve the existing VMs in their teamspace and create an empty group:

.. code-block:: python

   from lightning_sdk import Teamspace, VM, VMNetworkGroup

   teamspace = Teamspace("research", org="my-org")
   server = VM("k3s-server", teamspace=teamspace)
   worker = VM("k3s-worker", teamspace=teamspace)
   network = VMNetworkGroup.create(
       "k3s", teamspace=teamspace, cloud_account="my-machine-cluster-id"
   )
   network.attach(server, wait=True)

Later, add the worker and wait for the networking policy to be acknowledged:

.. code-block:: python

   network.attach(worker, wait=True)
   server_address = network.private_addresses[server.id]
   worker_address = network.private_addresses[worker.id]

The addresses are suitable for advertising node connectivity. Group networking
does not install Kubernetes or run its join command. The address uses NAT into
the guest's primary interface, so inbound services should listen on that interface
or all interfaces. Reserved internal service ports remain blocked between members.

``attach``, ``detach``, and ``set_members`` use the object's current revision.
A concurrent membership update raises ``VMNetworkGroupConflictError``; call
``refresh()`` and review membership before retrying. A wait also raises that error
if a newer revision replaces the requested membership. It does not silently
accept a different client's update.

Remove a node
-------------

Wait for revocation before reusing the node elsewhere:

.. code-block:: python

   network.detach(worker, wait=True)

Delete the group and wait for all affected hosts to release membership holds:

.. code-block:: python

   network.delete(wait=True)

Removal and deletion are available after the flag is disabled. An unavailable
host can keep revocation pending; a timeout does not force address reuse.
These operations do not delete the VMs.

Reference
---------

.. autoclass:: lightning_sdk.vm_network_group.VMNetworkGroup
   :members:

.. autoexception:: lightning_sdk.api.vm_network_group_api.VMNetworkGroupConflictError
