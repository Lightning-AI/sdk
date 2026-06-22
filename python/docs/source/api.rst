#############
API Reference
#############

This reference documents the public Lightning SDK surface.

Studio
======

.. currentmodule:: lightning_sdk

.. autoclass:: Studio
   :members:
   :show-inheritance:

.. autoclass:: VM
   :members:
   :show-inheritance:

Job
===

.. autoclass:: Job
   :members:
   :show-inheritance:

Machine
=======

.. autoclass:: Machine
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: CloudProvider
   :members:
   :undoc-members:
   :show-inheritance:

Teamspace
=========

.. autoclass:: Teamspace
   :members:
   :show-inheritance:

.. autoclass:: ConnectionType
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: FolderLocation
   :members:
   :undoc-members:
   :show-inheritance:

.. currentmodule:: lightning_sdk.api.teamspace_api

.. autoclass:: SecretType
   :members:
   :undoc-members:
   :show-inheritance:

.. currentmodule:: lightning_sdk

Plugins
=======

.. autoclass:: Plugin
   :members:
   :show-inheritance:

.. autoclass:: JobsPlugin
   :members:
   :show-inheritance:

.. autoclass:: MultiMachineTrainingPlugin
   :members:
   :show-inheritance:

.. autoclass:: SlurmJobsPlugin
   :members:
   :show-inheritance:

Multi-Machine Training
======================

.. autoclass:: MMT
   :members:
   :show-inheritance:

.. currentmodule:: lightning_sdk.mmt.base

.. autoclass:: MMTMachine
   :members:
   :show-inheritance:

Deployment
==========

.. currentmodule:: lightning_sdk

.. autoclass:: Deployment
   :members:
   :show-inheritance:

.. currentmodule:: lightning_sdk.api.deployment_api

.. autoclass:: Env
   :members:

.. autoclass:: Secret
   :members:

.. autoclass:: BasicAuth
   :members:

.. autoclass:: TokenAuth
   :members:

.. autoclass:: ApiKeyAuth
   :members:

.. autoclass:: ReleaseStrategy
   :members:

.. autoclass:: RollingUpdateReleaseStrategy
   :members:

.. autoclass:: HealthCheck
   :members:

.. autoclass:: ExecHealthCheck
   :members:

.. autoclass:: HttpHealthCheck
   :members:

.. autoclass:: AutoScalingMetric
   :members:

.. autoclass:: AutoScaleConfig
   :members:

.. autoclass:: RequestCaptureExportResult
   :members:

AI Hub
======

.. currentmodule:: lightning_sdk

.. autoclass:: AIHub
   :members:
   :show-inheritance:

Agent
=====

.. autoclass:: Agent
   :members:
   :show-inheritance:

K8s Cluster
===========

.. currentmodule:: lightning_sdk.k8s_cluster

.. autoclass:: K8sCluster
   :members:
   :show-inheritance:

.. autoclass:: K8sUsageResponse
   :members:

.. autoclass:: HourlyUsage
   :members:

Owner
=====

.. currentmodule:: lightning_sdk.owner

.. autoclass:: Owner
   :members:
   :show-inheritance:

Organization
============

.. currentmodule:: lightning_sdk

.. autoclass:: Organization
   :members:
   :show-inheritance:

User
====

.. autoclass:: User
   :members:
   :show-inheritance:

Status
======

.. autoclass:: Status
   :members:
   :undoc-members:
   :show-inheritance:

Models
======

.. currentmodule:: lightning_sdk.models

.. autoclass:: UploadedModelInfo
   :members:

.. currentmodule:: lightning_sdk.api.utils

.. autoclass:: Experiment
   :members:
