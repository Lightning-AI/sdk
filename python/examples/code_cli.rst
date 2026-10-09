Coding agents CLI examples
==========================

`code.lightning.ai <https://code.lightning.ai>`_ serves GLM-5.3, GLM-5.3 Flash and
DeepSeek V4.1 Flash to coding agents through an OpenAI-compatible API at
``https://code.lightning.ai/v1``. The ``lightning code`` commands set up a coding
tool to use it and create the API key it needs.

Requests bill the organization you pick, which needs a Pro, Teams or Enterprise
plan. A Free organization gets a link to upgrade instead of a key.

Set up OpenCode
---------------

.. code-block:: console

   $ pip install lightning-sdk -U
   $ lightning login
   $ curl -fsSL https://opencode.ai/install | bash

   $ lightning code setup opencode --org my-org
   OpenCode now uses code.lightning.ai, billed to My Org [my-org].
     Provider: lightning in ~/.config/opencode/opencode.json
     API key:  opencode on my-laptop 2026-10-09 in ~/.local/share/opencode/auth.json
     Default:  lightning/glm-5.3

   $ opencode

Without ``--org``, the command lists your organizations with their plans and asks
which one pays. In scripts and other non-interactive shells, ``--org`` is required.

The setup leaves the rest of OpenCode's config alone:

- The ``lightning`` provider is added to your global config, keeping its comments
  and other settings. The file is backed up as ``opencode.json.lightning-backup``
  first. `code/opencode.json <code/opencode.json>`_ is what a new config looks like.
- The API key goes to OpenCode's credential store, ``auth.json``, next to the keys
  ``opencode auth login`` saves, never into the config file. Its metadata records
  the organization and key, as in `code/opencode-auth.json <code/opencode-auth.json>`_.
- ``lightning/glm-5.3`` becomes the default model only if you have no default yet.
  Pass ``--model`` to set one anyway.

Preview the changes first, or pick a different default model:

.. code-block:: console

   $ lightning code setup opencode --org my-org --dry-run
   $ lightning code setup opencode --org my-org --model glm-5.3-flash

Run it again to switch organizations, which creates a key there and revokes the
old one, or to pick up new models. ``--rotate-key`` replaces the key in place.

Check and undo the setup
------------------------

.. code-block:: console

   $ lightning code status
   OpenCode
     Org:     my-org
     API key: opencode on my-laptop 2026-10-09 (01jexamplekey0000000000000)
     Config:  ~/.config/opencode/opencode.json
     Default: lightning/glm-5.3

   $ lightning code remove opencode

``remove`` takes out the provider, a default model on it, and the key,
which it also revokes. Pass ``--keep-key`` to leave the key active.

Use other tools
---------------

``lightning code token`` creates a key for anything else that speaks the OpenAI
or Anthropic API. The key is printed once, so store it straight away.

.. code-block:: console

   $ export OPENAI_BASE_URL=https://code.lightning.ai/v1
   $ export OPENAI_API_KEY=$(lightning code token --org my-org)

   $ export ANTHROPIC_BASE_URL=https://code.lightning.ai
   $ export ANTHROPIC_AUTH_TOKEN=$(lightning code token --org my-org --name claude-code)
   $ claude --model glm-5.3

   $ lightning code token --org my-org --json

Keys created this way are listed and deleted with ``lightning api-key``.
