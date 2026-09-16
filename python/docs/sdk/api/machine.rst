Machine
=======

.. currentmodule:: lightning_sdk

H200 machines support one, two, four, and eight GPUs via ``Machine.H200``,
``Machine.H200_X_2``, ``Machine.H200_X_4``, and ``Machine.H200_X_8``; B200 machines
support one and eight via ``Machine.B200`` and ``Machine.B200_X_8``.
Use the same names on every cloud, or ``--gpus H200:2`` in the CLI.
Availability depends on the selected cloud and account.

.. autoclass:: Machine
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: CloudProvider
   :members:
   :undoc-members:
   :show-inheritance:
