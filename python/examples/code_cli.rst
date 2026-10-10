Coding agents CLI examples
==========================

`code.lightning.ai <https://code.lightning.ai>`_ serves GLM-5.3, GLM-5.3 Flash and
DeepSeek V4.1 Flash to coding agents through an OpenAI-compatible API at
``https://code.lightning.ai/v1``. The ``lightning code`` commands set up a coding
tool to use it and create the API key it needs. They work the same on macOS and
Linux.

Requests bill the organization you pick, which needs a Pro, Teams or Enterprise
plan. A Free organization gets a link to upgrade instead of a key.

Set up a tool
-------------

.. code-block:: console

   $ pip install lightning-sdk -U
   $ lightning login

   $ lightning code setup opencode --org my-org
   OpenCode now uses code.lightning.ai, billed to My Org [my-org].
     Provider: lightning in ~/.config/opencode/opencode.json
     Key file: ~/.local/share/opencode/auth.json
     API key:  opencode on my-laptop 2026-10-09
     Default:  lightning/deepseek-v4.1-flash

The tool is one of ``opencode``, ``pi``, ``codex``, ``dsh`` (DeepSeek Harness) or
``cursor``. Without ``--org``, the command lists your organizations with their
plans and asks which one pays. In scripts and other non-interactive shells,
``--org`` is required.

For every tool, the setup:

- Adds Lightning as a provider called ``lightning`` and leaves the rest of the
  tool's config alone, comments included. A config file you already had is backed
  up as ``<file>.lightning-backup`` first. Files that hold keys aren't copied.
- Saves the API key where the tool keeps its own keys, never in a file you'd
  share or commit.
- Makes ``deepseek-v4.1-flash`` the default model only if you have no default yet.
  Pass ``--model`` to set one anyway.
- Takes the models, with their names, context windows, output limits and image
  support, from ``https://code.lightning.ai/v1/models``, so new models appear
  without a CLI update. If it can't be reached, a built-in list is used.

Preview the changes first, or pick a different default model:

.. code-block:: console

   $ lightning code setup pi --org my-org --dry-run
   $ lightning code setup pi --org my-org --model glm-5.3

Run it again to switch organizations, which creates a key there and revokes the
old one, or to pick up new models. ``--rotate-key`` replaces the key in place.
``--force`` replaces a Lightning setup you made by hand.

OpenCode
--------

.. code-block:: console

   $ curl -fsSL https://opencode.ai/install | bash
   $ lightning code setup opencode --org my-org
   $ opencode

The provider goes into ``~/.config/opencode/opencode.json`` (or ``opencode.jsonc``)
and the key into OpenCode's ``~/.local/share/opencode/auth.json``. If your config
limits providers with ``enabled_providers``, ``lightning`` is added to it. See
`code/opencode.json <code/opencode.json>`_ and
`code/opencode-auth.json <code/opencode-auth.json>`_.

pi
--

.. code-block:: console

   $ curl -fsSL https://pi.dev/install.sh | sh
   $ lightning code setup pi --org my-org
   $ pi

The provider goes into ``~/.pi/agent/models.json``, the key into pi's
``auth.json`` and the default model into ``settings.json``, all under
``$PI_CODING_AGENT_DIR`` when it's set. See `code/pi-models.json <code/pi-models.json>`_
and `code/pi-settings.json <code/pi-settings.json>`_.

Codex
-----

.. code-block:: console

   $ npm install -g @openai/codex
   $ lightning code setup codex --org my-org
   $ codex --profile lightning
   $ codex --profile lightning -m lightning-ai/glm-5.3

Codex gets a profile of its own, ``~/.codex/lightning.config.toml``, which it
layers over your ``config.toml`` when started with ``--profile lightning``, so
your usual Codex setup doesn't change. The profile holds the key and only you can
read it. See `code/codex-lightning.config.toml <code/codex-lightning.config.toml>`_.

Codex talks to code.lightning.ai over the Responses API. Image input through
Codex isn't supported yet; the other tools send images fine.

DeepSeek Harness
----------------

.. code-block:: console

   $ npm install -g @deepseek-ai/dsh     # needs Node.js 22.19 or newer
   $ lightning code setup dsh --org my-org
   $ dsh web

The provider and default model go into the ``web`` and ``headless`` profiles,
``~/.dsh/profiles/<profile>/cordis.patch.yml``, next to your other entries. The
key goes into dsh's ``~/.dsh/.credentials.yaml`` as ``LIGHTNING_CODE_API_KEY``.
See `code/dsh-cordis.patch.yml <code/dsh-cordis.patch.yml>`_ and
`code/dsh-credentials.yaml <code/dsh-credentials.yaml>`_.

Cursor
------

Cursor keeps these settings where nothing outside it can safely change them, so
the setup creates a key and prints the steps to add it in Cursor Settings:

.. code-block:: console

   $ lightning code setup cursor --org my-org
   Cursor now uses code.lightning.ai, billed to My Org [my-org].
     API key: cursor on my-laptop 2026-10-09

   Finish in Cursor (needs a paid Cursor plan):
     1. Open Cursor Settings (Cmd+Shift+J on macOS, Ctrl+Shift+J elsewhere) and go to Models.
     2. Under API Keys, paste this into OpenAI API Key and press Enter:
          sk-lit-...
     3. Turn on "Use OpenAI API Key".
     4. Turn on "Override OpenAI Base URL" and enter:
          https://code.lightning.ai/v1
     5. At the top of Models, add these model names and make sure they're switched on:
          lightning-ai/glm-5.3
          lightning-ai/glm-5.3-flash
          lightning-ai/deepseek-v4.1-flash
     6. Open a new chat and pick lightning-ai/deepseek-v4.1-flash.

While the base URL override is on, Cursor sends all OpenAI models to Lightning,
so its own GPT and Auto models stop working until you turn it off. The
``cursor-agent`` CLI can't use Lightning models.

Check and undo the setup
------------------------

.. code-block:: console

   $ lightning code status
   OpenCode: billed to my-org
     API key: opencode on my-laptop 2026-10-09 (01jexamplekey0000000000000)
     Config:  ~/.config/opencode/opencode.json
     Default: lightning/deepseek-v4.1-flash
   pi: not set up
   Codex: billed to my-org
     ...

   $ lightning code remove opencode

``remove`` takes out the provider, a Lightning default model, and the key, which
it also revokes. Files the setup created are deleted again. Pass ``--keep-key`` to
leave the key active.

Use other tools
---------------

``lightning code token`` creates a key for anything else that speaks the OpenAI
or Anthropic API. The key is printed once, so store it straight away.

.. code-block:: console

   $ export OPENAI_BASE_URL=https://code.lightning.ai/v1
   $ export OPENAI_API_KEY=$(lightning code token --org my-org)

   $ export ANTHROPIC_BASE_URL=https://code.lightning.ai
   $ export ANTHROPIC_AUTH_TOKEN=$(lightning code token --org my-org --name claude-code)
   $ claude --model deepseek-v4.1-flash

   $ lightning code token --org my-org --json

Keys created this way are listed and deleted with ``lightning api-key``.
