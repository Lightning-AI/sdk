Raw API CLI examples
====================

Use ``lightning-sdk api`` when you need an authenticated request to a Lightning
API endpoint that does not have a dedicated CLI command yet. The command uses
your current Lightning credentials and prints the JSON response.

Prerequisites
-------------

.. code-block:: console

   $ pip install lightning-sdk -U
   $ lightning login
   $ jq --version

Find teamspace IDs
------------------

List the teamspaces and projects available to the current user:

.. code-block:: console

   $ lightning-sdk api /v1/memberships

Print only teamspace names:

.. code-block:: console

   $ lightning-sdk api /v1/memberships | jq -r '.memberships[].name'

Print teamspace IDs with their names. Use the ID as ``PROJECT_ID`` in
project-scoped raw API calls:

.. code-block:: console

   $ lightning-sdk api /v1/memberships | jq -r '.memberships[] | [.projectId, .name] | @tsv'
   $ export PROJECT_ID="replace-with-project-id"

List jobs
---------

Use the jobs API when a script needs fields that are not exposed by
``lightning job list``.

.. code-block:: console

   $ lightning-sdk api "/v1/projects/${PROJECT_ID}/jobs" -X GET -F limit=20
   $ lightning-sdk api "/v1/projects/${PROJECT_ID}/jobs" -X GET -F limit=20 | jq -r '.jobs[].name'

List deployments
----------------

Use the deployments API to inspect deployment payloads directly:

.. code-block:: console

   $ lightning-sdk api "/v1/projects/${PROJECT_ID}/deployments" -X GET -F limit=20
   $ lightning-sdk api "/v1/projects/${PROJECT_ID}/deployments" -X GET -F limit=20 | jq -r '.deployments[].name'

List sandboxes
--------------

Sandbox endpoints are organization-scoped. Set ``ORG_ID`` explicitly, or derive
the first organization owner ID from memberships:

.. code-block:: console

   $ export ORG_ID="$(lightning-sdk api /v1/memberships | jq -r '[.memberships[] | select(.ownerType == "organization") | .ownerId][0]')"
   $ lightning-sdk api /v1/core/sandboxes -X GET -f "organizationId=${ORG_ID}" -f "projectId=${PROJECT_ID}" -f limit=20
   $ lightning-sdk api /v1/core/sandboxes -X GET -f "organizationId=${ORG_ID}" -f "projectId=${PROJECT_ID}" -f limit=20 | jq -r '.sandboxes[] | .name // .id'
