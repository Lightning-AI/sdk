Machine
=======

.. currentmodule:: lightning_sdk

H200 machines support one, two, four, and eight GPUs via ``Machine.H200``,
``Machine.H200_X_2``, ``Machine.H200_X_4``, and ``Machine.H200_X_8``.
Use the same names on every cloud, or ``--gpus H200:2`` in the CLI.
The SDK selects the Lightning Compute identifier internally for machine-provider
cloud accounts. Availability depends on the selected cloud and account.

.. autoclass:: Machine
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: CloudProvider
   :members:
   :undoc-members:
   :show-inheritance:
