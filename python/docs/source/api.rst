#############
API Reference
#############

The Lightning SDK is the Python interface for managing Lightning AI resources
from scripts, notebooks, services, and CI jobs. Use it when you need the same
resource control exposed by the CLI, but want it inside Python code with typed
objects, method references, and reusable application logic.

Install
*******

Install or upgrade the package:

.. code-block:: bash

   pip install lightning-sdk -U

Authenticate
************

For local development, authenticate once with the CLI:

.. code-block:: bash

   lightning login

For automation, configure credentials with environment variables:

.. code-block:: bash

   export LIGHTNING_USER_ID=your-user-id
   export LIGHTNING_API_KEY=your-api-key

Core Resources
**************

Studios are persistent development environments. Start with
:class:`~lightning_sdk.Studio` when you need to create or control an
interactive workspace, and use :class:`~lightning_sdk.VM` or
:class:`~lightning_sdk.Machine` when selecting compute.

Jobs run code in managed cloud compute. Use :meth:`lightning_sdk.Job.run` for
single-node work and :meth:`lightning_sdk.MMT.run` for multi-machine training.

Deployments turn model servers and applications into managed services. Use
:class:`~lightning_sdk.Deployment` with the deployment helper classes in
:doc:`api/deployment` for environment variables, secrets, authentication,
health checks, and rollout behavior.

Teamspaces, organizations, and users define the account context for SDK calls.
Use :class:`~lightning_sdk.Teamspace`, :class:`~lightning_sdk.Organization`,
and :class:`~lightning_sdk.User` when you need to resolve or switch the scope
of an operation.

Quick Example
*************

.. code-block:: python

   from lightning_sdk import Machine, Studio

   studio = Studio("my-studio")
   studio.start()

   job = studio.run("python train.py", machine=Machine.A10G)
   job.wait()

   studio.stop()

Reference Pages
***************

.. toctree::
   :maxdepth: 1

   api/studio
   api/job
   api/machine
   api/teamspace
   api/mmt
   api/deployment
   api/agent
   api/k8s-cluster
   api/owner
   api/organization
   api/user
   api/status
   api/models
   api/experiment
