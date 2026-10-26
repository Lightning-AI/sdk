Coding agents CLI examples
==========================

`code.lightning.ai <https://code.lightning.ai>`_ serves GLM-5.3, GLM-5.3 Flash and
DeepSeek V4.1 Flash to coding agents through an OpenAI-compatible API at
``https://code.lightning.ai/v1``. The ``lightning code`` commands set up a coding
tool to use it with the API key in ``LIGHTNING_API_KEY``. They work the same on
macOS and Linux.

Requests bill the organization the key belongs to. ``lightning code`` doesn't
create keys, so make one in advance and export it.

Set up a tool
-------------

.. code-block:: console

   $ pip install lightning-sdk -U
   $ export LIGHTNING_API_KEY=lit_sa_...

   $ lightning code setup opencode
   OpenCode now uses code.lightning.ai.
     Provider: lightning in ~/.config/opencode/opencode.json
     Key file: ~/.local/share/opencode/auth.json
     Default:  lightning/deepseek-v4.1-flash

The tool is one of ``opencode``, ``pi``, ``codex``, ``dsh`` (DeepSeek Harness) or
``cursor``. The key is read from ``LIGHTNING_API_KEY`` and saved in the tool's own
config; if the variable isn't set, setup stops and says so.

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

   $ lightning code setup pi --dry-run
   $ lightning code setup pi --model glm-5.3

Run it again after changing ``LIGHTNING_API_KEY``, or to pick up new models.
``--force`` replaces a Lightning setup you made by hand.

OpenCode
--------

.. code-block:: console

   $ curl -fsSL https://opencode.ai/install | bash
   $ lightning code setup opencode
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
   $ lightning code setup pi
   $ pi

The provider goes into ``~/.pi/agent/models.json``, the key into pi's
``auth.json`` and the default model into ``settings.json``, all under
``$PI_CODING_AGENT_DIR`` when it's set. See `code/pi-models.json <code/pi-models.json>`_
and `code/pi-settings.json <code/pi-settings.json>`_.

Codex
-----

.. code-block:: console

   $ npm install -g @openai/codex
   $ lightning code setup codex
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
   $ lightning code setup dsh
   $ dsh web

The provider and default model go into the ``web`` and ``headless`` profiles,
``~/.dsh/profiles/<profile>/cordis.patch.yml``, next to your other entries. The
key goes into dsh's ``~/.dsh/.credentials.yaml`` as ``LIGHTNING_CODE_API_KEY``.
See `code/dsh-cordis.patch.yml <code/dsh-cordis.patch.yml>`_ and
`code/dsh-credentials.yaml <code/dsh-credentials.yaml>`_.

Cursor
------

Cursor keeps these settings where nothing outside it can safely change them, so
the setup prints the key from ``LIGHTNING_API_KEY`` and the steps to add it in
Cursor Settings:

.. code-block:: console

   $ lightning code setup cursor
   Finish in Cursor (needs a paid Cursor plan):
     1. Open Cursor Settings (Cmd+Shift+J on macOS, Ctrl+Shift+J elsewhere) and go to Models.
     2. Under API Keys, paste this into OpenAI API Key and press Enter:
          lit_sa_...
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
   OpenCode: set up by `lightning code`
     Config:  ~/.config/opencode/opencode.json
     Default: lightning/deepseek-v4.1-flash
   pi: not set up
   Codex: set up by `lightning code`
     ...

   $ lightning code remove opencode

``remove`` takes out the provider, a Lightning default model, and the key saved in
the tool's config. Files the setup created are deleted again. No key is revoked,
because ``lightning code`` doesn't create keys; revoke a key you no longer need in
the web UI.
