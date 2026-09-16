Machine
=======

.. currentmodule:: lightning_sdk

H200 machines support one, two, four, and eight GPUs. Use ``Machine.H200`` and
``Machine.H200_X_2`` / ``H200_X_4`` / ``H200_X_8`` for the existing cloud-provider
H200 types. For Lightning Compute H200 141 GB machines, use ``Machine.H200_141GB``
and ``Machine.H200_141GB_X_2`` / ``H200_141GB_X_4`` / ``H200_141GB_X_8``.
The corresponding CLI GPU selectors are ``--gpus H200:2`` and
``--gpus H200_141GB:2``. Availability depends on the selected cloud and account.

.. autoclass:: Machine
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: CloudProvider
   :members:
   :undoc-members:
   :show-inheritance:
