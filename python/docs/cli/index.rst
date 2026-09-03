Command Line Interface
++++++++++++++++++++++

The Python package installs the ``lightning`` command. The ``lightning-sdk``
console script is an alias for the same command group.

Use the CLI when you want to manage Lightning AI resources from a terminal,
CI job, shell script, or other automation.

.. lightning-reference:: main_cli
   :root-label: lightning
   :anchor-prefix: lightning

   from lightning_sdk.cli.entrypoint import main_cli

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

   export LIGHTNING_API_KEY=your-api-key

Shell completion
----------------

Install native shell completion for your current shell:

.. code-block:: bash

   lightning completion install

Supported shells are Zsh, Fish, and Bash 4.4 or newer.

Pass the shell explicitly when it cannot be detected from ``$SHELL``:

.. code-block:: bash

   lightning completion install --shell zsh

The installer writes a static completion script and configures Bash or Zsh to
source it. Fish uses its native auto-loaded completions directory. This avoids
importing the CLI while the shell starts. Check or remove the installation with:

.. code-block:: bash

   lightning completion status
   lightning completion uninstall

Local paths are completed by the shell. Paths beginning with ``lit://`` are
resolved dynamically from accessible Teamspaces, Studios, and remote files
without opening interactive CLI prompts. Resource options also complete
dynamically, including ``--teamspace owner/teamspace`` and existing Studio
selectors such as ``lightning studio stop --name`` when a Teamspace is selected
or configured.

Usage
-----

Run a command group directly:

.. code-block:: bash

   lightning [command]

Every command and subcommand exposes help directly:

.. code-block:: bash

   lightning COMMAND --help

Common Workflows
----------------

* Develop interactively with :doc:`studio`.
* Submit and inspect training or batch work with :doc:`job` and :doc:`mmt`.
* Tail, follow, and search a run's logs with its own ``logs`` command — see
  :doc:`job`, :doc:`mmt`, :doc:`deployment`, and :doc:`sandbox`.
* Build and operate inference services with :doc:`deployment` and :doc:`model`.
* Move data and artifacts with :doc:`file`, :doc:`folder`, :doc:`container`, and :doc:`cp`.
* Configure accounts, organizations, teamspaces, cloud accounts, and SSH with
  :doc:`config`, :doc:`api-key`, and :doc:`ssh`.
* Manage lower-level sandbox sessions with :doc:`sandbox`.
* Run plain cloud VMs you SSH into yourself with :doc:`instance`.

Command details
---------------

The pages below keep focused URLs for each command group and its full option
reference.

.. toctree::
   :maxdepth: 1

   config
   job
   mmt
   machine
   instance
   deployment
   container
   model
   api-key
   file
   folder
   ssh
   studio
   sandbox
   base-studio
   license
   cp
