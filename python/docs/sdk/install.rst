############
Installation
############

Requirements
============

- Python 3.8 or later
- A `Lightning AI <https://lightning.ai>`_ account

Install
=======

Install from PyPI:

.. code-block:: bash

    pip install lightning-sdk

For model serving support:

.. code-block:: bash

    pip install "lightning-sdk[serve]"

Authentication
==============

Log in via the CLI before using the SDK:

.. code-block:: bash

    lightning login

This stores credentials locally and is required for all API calls.
You can also set the ``LIGHTNING_API_KEY`` environment variable to authenticate
non-interactively in CI or headless environments.
