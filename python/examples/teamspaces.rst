Teamspaces SDK tutorial
=======================

A teamspace is the account context for Lightning AI resources. Studios, jobs,
MMTs, models, secrets, machines, and cloud accounts are all scoped through a
teamspace. Most workflows start by choosing a teamspace explicitly, then pass
that same context to every SDK object.

Prerequisites
-------------

Install and authenticate:

.. code-block:: console

   $ pip install lightning-sdk -U
   $ lightning login

Construct a ``Teamspace`` when Python code should keep the account context in
one object and pass it to other SDK resources:

.. literalinclude:: ../../../examples/teamspaces.py
   :language: python
   :start-after: # sdk-teamspace-inspect-start
   :end-before: # sdk-teamspace-inspect-end
   :dedent: 8

Use the same object when launching resources so the teamspace cannot silently
come from process config:

.. literalinclude:: ../../../examples/teamspaces.py
   :language: python
   :start-after: # sdk-teamspace-job-start
   :end-before: # sdk-teamspace-job-end
   :dedent: 8

Manage secrets through the SDK when application code needs to create or update
teamspace-level secret references:

.. literalinclude:: ../../../examples/teamspaces.py
   :language: python
   :start-after: # sdk-teamspace-secret-start
   :end-before: # sdk-teamspace-secret-end
   :dedent: 8

Do not hard-code secret values in source files. Load them from your secret
manager or environment at runtime, then pass them to ``set_secret``.

Run the companion script directly when you want to execute the SDK example:

.. code-block:: console

   $ python python/examples/teamspaces.py --teamspace teamspace --org owner inspect
   $ HF_TOKEN=... python python/examples/teamspaces.py --teamspace teamspace --org owner set-secret

Operational notes
-----------------

- Prefer ``Teamspace("name", org="owner")`` or ``Teamspace("name", user="owner")``
  in SDK code instead of relying on ambient config.
- The SDK raises when it cannot infer whether the owner is a user or
  organization. Passing ``org=`` or ``user=`` removes that ambiguity.
- Teamspace resource listings check permissions; a permission error means the
  authenticated identity cannot access that resource family in the teamspace.
