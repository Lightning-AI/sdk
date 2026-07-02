Command Line Interface
======================

The Python package installs the ``lightning`` command. The ``lightning-sdk``
console script is an alias for the same command group.

Use the CLI when you want to manage Lightning AI resources from a terminal,
CI job, shell script, or other automation. The command reference below is
generated from the Click command tree, so command groups, options, arguments,
and examples stay aligned with the installed package.

Install
-------

Install or upgrade the Python package:

.. code-block:: bash

   pip install lightning-sdk -U

Authenticate
------------

For interactive use, sign in with:

.. code-block:: bash

   lightning login

For non-interactive environments, configure credentials through environment
variables instead:

.. code-block:: bash

   export LIGHTNING_USER_ID=your-user-id
   export LIGHTNING_API_KEY=your-api-key

Usage
-----

Run a command group directly:

.. code-block:: bash

   lightning [command]

Every command and subcommand exposes help from the same Click definitions used
by this reference:

.. code-block:: bash

   lightning COMMAND --help

Common Workflows
----------------

- Develop interactively with :doc:`cli/studio`.
- Submit and inspect training or batch work with :doc:`cli/job` and
  :doc:`cli/mmt`.
- Build and operate inference services with :doc:`cli/deployment` and
  :doc:`cli/model`.
- Move data and artifacts with :doc:`cli/file`, :doc:`cli/folder`,
  :doc:`cli/container`, and :doc:`cli/cp`.
- Configure accounts, organizations, teamspaces, cloud accounts, and SSH with
  :doc:`cli/config`, :doc:`cli/api-key`, and :doc:`cli/ssh`.
- Manage lower-level sandbox sessions with :doc:`cli/sandbox`.

Command Groups
--------------

.. toctree::
   :maxdepth: 1

   cli/config
   cli/job
   cli/mmt
   cli/machine
   cli/deployment
   cli/container
   cli/model
   cli/api-key
   cli/file
   cli/folder
   cli/ssh
   cli/studio
   cli/sandbox
   cli/base-studio
   cli/license
   cli/cp

.. click:: lightning_sdk.cli.entrypoint:main_cli
   :prog: lightning
   :nested: short
