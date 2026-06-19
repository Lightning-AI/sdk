/* eslint-disable */
/* tslint:disable */
// @ts-nocheck
/*
 * ---------------------------------------------------------------
 * ## THIS FILE WAS GENERATED VIA SWAGGER-TYPESCRIPT-API        ##
 * ##                                                           ##
 * ## AUTHOR: acacode                                           ##
 * ## SOURCE: https://github.com/acacode/swagger-typescript-api ##
 * ---------------------------------------------------------------
 */

import {
  RpcStatus,
  SandboxesServiceCreateSandboxDirectoryBody,
  SandboxesServiceCreateSandboxSnapshotBody,
  SandboxesServiceExtendSandboxTimeoutBody,
  SandboxesServiceFinalizeSandboxSnapshotBody,
  SandboxesServiceGetSandboxSnapshotBlobDownloadUrlsBody,
  SandboxesServiceGetSandboxSnapshotBlobUploadUrlsBody,
  SandboxesServiceRunSandboxCommandBody,
  SandboxesServiceStopSandboxBody,
  SandboxesServiceUpdateSandboxBody,
  SandboxesServiceWriteSandboxFileBody,
  V1CreateSandboxDirectoryResponse,
  V1CreateSandboxRequest,
  V1DeleteSandboxResponse,
  V1DeleteSandboxSnapshotResponse,
  V1ExtendSandboxTimeoutResponse,
  V1GetSandboxCommandLogsResponse,
  V1GetSandboxCommandResponse,
  V1GetSandboxFileResponse,
  V1GetSandboxSnapshotBlobDownloadUrlsResponse,
  V1GetSandboxSnapshotBlobUploadUrlsResponse,
  V1KillSandboxCommandResponse,
  V1ListSandboxCommandsResponse,
  V1ListSandboxSnapshotsResponse,
  V1ListSandboxesResponse,
  V1RunSandboxCommandResponse,
  V1Sandbox,
  V1SandboxSnapshot,
  V1StopSandboxResponse,
  V1WriteSandboxFileResponse,
} from "./data-contracts";
import { ContentType, HttpClient, RequestParams } from "./http-client";

export class SandboxesService<
  SecurityDataType = unknown,
> extends HttpClient<SecurityDataType> {
  /**
   * No description
   *
   * @tags SandboxesService
   * @name SandboxesServiceListSandboxes
   * @summary Sandboxes
   * @request GET:/v1/core/sandboxes
   */
  sandboxesServiceListSandboxes = (
    query?: {
      organizationId?: string;
      pageToken?: string;
      /** @format int64 */
      limit?: string;
      /**
       * Optional teamspace/project scoping. When set, only sandboxes belonging
       * to this project are returned. Mirrors `ListSandboxSnapshotsRequest`.
       * Sandboxes created before this field landed have no `project_id`
       * persisted server-side, so filtering will return an empty set until
       * sandboxes are recreated with a project context.
       */
      projectId?: string;
    },
    params: RequestParams = {},
  ) =>
    this.request<V1ListSandboxesResponse, RpcStatus>({
      path: `/v1/core/sandboxes`,
      method: "GET",
      query: query,
      format: "json",
      ...params,
    });
  /**
   * No description
   *
   * @tags SandboxesService
   * @name SandboxesServiceCreateSandbox
   * @request POST:/v1/core/sandboxes
   */
  sandboxesServiceCreateSandbox = (
    body: V1CreateSandboxRequest,
    params: RequestParams = {},
  ) =>
    this.request<V1Sandbox, RpcStatus>({
      path: `/v1/core/sandboxes`,
      method: "POST",
      body: body,
      type: ContentType.Json,
      format: "json",
      ...params,
    });
  /**
   * No description
   *
   * @tags SandboxesService
   * @name SandboxesServiceListSandboxSnapshots
   * @summary Snapshots
   * @request GET:/v1/core/sandboxes/snapshots
   */
  sandboxesServiceListSandboxSnapshots = (
    query?: {
      organizationId?: string;
      pageToken?: string;
      /** @format int64 */
      limit?: string;
      projectId?: string;
      name?: string;
      sortOrder?: string;
    },
    params: RequestParams = {},
  ) =>
    this.request<V1ListSandboxSnapshotsResponse, RpcStatus>({
      path: `/v1/core/sandboxes/snapshots`,
      method: "GET",
      query: query,
      format: "json",
      ...params,
    });
  /**
   * No description
   *
   * @tags SandboxesService
   * @name SandboxesServiceGetSandboxSnapshot
   * @request GET:/v1/core/sandboxes/snapshots/{snapshotId}
   */
  sandboxesServiceGetSandboxSnapshot = (
    snapshotId: string,
    query?: {
      organizationId?: string;
    },
    params: RequestParams = {},
  ) =>
    this.request<V1SandboxSnapshot, RpcStatus>({
      path: `/v1/core/sandboxes/snapshots/${snapshotId}`,
      method: "GET",
      query: query,
      format: "json",
      ...params,
    });
  /**
   * No description
   *
   * @tags SandboxesService
   * @name SandboxesServiceDeleteSandboxSnapshot
   * @request DELETE:/v1/core/sandboxes/snapshots/{snapshotId}
   */
  sandboxesServiceDeleteSandboxSnapshot = (
    snapshotId: string,
    query?: {
      organizationId?: string;
    },
    params: RequestParams = {},
  ) =>
    this.request<V1DeleteSandboxSnapshotResponse, RpcStatus>({
      path: `/v1/core/sandboxes/snapshots/${snapshotId}`,
      method: "DELETE",
      query: query,
      format: "json",
      ...params,
    });
  /**
 * No description
 *
 * @tags SandboxesService
 * @name SandboxesServiceGetSandboxSnapshotBlobDownloadUrls
 * @summary GetSandboxSnapshotBlobDownloadUrls mints presigned GET URLs for a
batch of sha256 digests so the restoring agent can pull missing
blobs from S3 directly. One URL per digest, in request order.
 * @request POST:/v1/core/sandboxes/snapshots/{snapshotId}/blobs/download-urls
 */
  sandboxesServiceGetSandboxSnapshotBlobDownloadUrls = (
    snapshotId: string,
    body: SandboxesServiceGetSandboxSnapshotBlobDownloadUrlsBody,
    params: RequestParams = {},
  ) =>
    this.request<V1GetSandboxSnapshotBlobDownloadUrlsResponse, RpcStatus>({
      path: `/v1/core/sandboxes/snapshots/${snapshotId}/blobs/download-urls`,
      method: "POST",
      body: body,
      type: ContentType.Json,
      format: "json",
      ...params,
    });
  /**
 * No description
 *
 * @tags SandboxesService
 * @name SandboxesServiceGetSandboxSnapshotBlobUploadUrls
 * @summary GetSandboxSnapshotBlobUploadUrls performs an existence check on
the supplied sha256 digests in the cluster blob store and returns
presigned PUT URLs only for those not already present. Existing
digests are echoed back in `existing_digests` so the caller can
skip uploading them.
 * @request POST:/v1/core/sandboxes/snapshots/{snapshotId}/blobs/upload-urls
 */
  sandboxesServiceGetSandboxSnapshotBlobUploadUrls = (
    snapshotId: string,
    body: SandboxesServiceGetSandboxSnapshotBlobUploadUrlsBody,
    params: RequestParams = {},
  ) =>
    this.request<V1GetSandboxSnapshotBlobUploadUrlsResponse, RpcStatus>({
      path: `/v1/core/sandboxes/snapshots/${snapshotId}/blobs/upload-urls`,
      method: "POST",
      body: body,
      type: ContentType.Json,
      format: "json",
      ...params,
    });
  /**
 * No description
 *
 * @tags SandboxesService
 * @name SandboxesServiceFinalizeSandboxSnapshot
 * @summary FinalizeSandboxSnapshot flips the row from "saving" to "ready"
after the agent has uploaded every blob and the manifest body to
`object_key`. The controlplane records final size_bytes +
rootfs_digest from the manifest.
 * @request POST:/v1/core/sandboxes/snapshots/{snapshotId}/finalize
 */
  sandboxesServiceFinalizeSandboxSnapshot = (
    snapshotId: string,
    body: SandboxesServiceFinalizeSandboxSnapshotBody,
    params: RequestParams = {},
  ) =>
    this.request<V1SandboxSnapshot, RpcStatus>({
      path: `/v1/core/sandboxes/snapshots/${snapshotId}/finalize`,
      method: "POST",
      body: body,
      type: ContentType.Json,
      format: "json",
      ...params,
    });
  /**
   * No description
   *
   * @tags SandboxesService
   * @name SandboxesServiceGetSandbox
   * @request GET:/v1/core/sandboxes/{id}
   */
  sandboxesServiceGetSandbox = (
    id: string,
    query?: {
      organizationId?: string;
    },
    params: RequestParams = {},
  ) =>
    this.request<V1Sandbox, RpcStatus>({
      path: `/v1/core/sandboxes/${id}`,
      method: "GET",
      query: query,
      format: "json",
      ...params,
    });
  /**
   * No description
   *
   * @tags SandboxesService
   * @name SandboxesServiceDeleteSandbox
   * @request DELETE:/v1/core/sandboxes/{id}
   */
  sandboxesServiceDeleteSandbox = (
    id: string,
    query?: {
      organizationId?: string;
    },
    params: RequestParams = {},
  ) =>
    this.request<V1DeleteSandboxResponse, RpcStatus>({
      path: `/v1/core/sandboxes/${id}`,
      method: "DELETE",
      query: query,
      format: "json",
      ...params,
    });
  /**
 * No description
 *
 * @tags SandboxesService
 * @name SandboxesServiceUpdateSandbox
 * @summary UpdateSandbox updates a sandbox in place. Currently the only
supported mutation is `resume = true`, which resumes a previously
stopped persistent sandbox from its most recent auto-snapshot while
preserving the sandbox id. Modelled on Vercel's update-sandbox
endpoint:
https://vercel.com/docs/rest-api/sandboxes-v2-beta/update-a-sandbox.
 * @request PATCH:/v1/core/sandboxes/{id}
 */
  sandboxesServiceUpdateSandbox = (
    id: string,
    body: SandboxesServiceUpdateSandboxBody,
    params: RequestParams = {},
  ) =>
    this.request<V1Sandbox, RpcStatus>({
      path: `/v1/core/sandboxes/${id}`,
      method: "PATCH",
      body: body,
      type: ContentType.Json,
      format: "json",
      ...params,
    });
  /**
   * No description
   *
   * @tags SandboxesService
   * @name SandboxesServiceListSandboxCommands
   * @request GET:/v1/core/sandboxes/{id}/commands
   */
  sandboxesServiceListSandboxCommands = (
    id: string,
    query?: {
      organizationId?: string;
    },
    params: RequestParams = {},
  ) =>
    this.request<V1ListSandboxCommandsResponse, RpcStatus>({
      path: `/v1/core/sandboxes/${id}/commands`,
      method: "GET",
      query: query,
      format: "json",
      ...params,
    });
  /**
   * No description
   *
   * @tags SandboxesService
   * @name SandboxesServiceRunSandboxCommand
   * @request POST:/v1/core/sandboxes/{id}/commands
   */
  sandboxesServiceRunSandboxCommand = (
    id: string,
    body: SandboxesServiceRunSandboxCommandBody,
    params: RequestParams = {},
  ) =>
    this.request<V1RunSandboxCommandResponse, RpcStatus>({
      path: `/v1/core/sandboxes/${id}/commands`,
      method: "POST",
      body: body,
      type: ContentType.Json,
      format: "json",
      ...params,
    });
  /**
   * No description
   *
   * @tags SandboxesService
   * @name SandboxesServiceGetSandboxCommand
   * @request GET:/v1/core/sandboxes/{id}/commands/{cmdId}
   */
  sandboxesServiceGetSandboxCommand = (
    id: string,
    cmdId: string,
    query?: {
      organizationId?: string;
    },
    params: RequestParams = {},
  ) =>
    this.request<V1GetSandboxCommandResponse, RpcStatus>({
      path: `/v1/core/sandboxes/${id}/commands/${cmdId}`,
      method: "GET",
      query: query,
      format: "json",
      ...params,
    });
  /**
   * No description
   *
   * @tags SandboxesService
   * @name SandboxesServiceKillSandboxCommand
   * @request POST:/v1/core/sandboxes/{id}/commands/{cmdId}/kill
   */
  sandboxesServiceKillSandboxCommand = (
    id: string,
    cmdId: string,
    query?: {
      organizationId?: string;
    },
    params: RequestParams = {},
  ) =>
    this.request<V1KillSandboxCommandResponse, RpcStatus>({
      path: `/v1/core/sandboxes/${id}/commands/${cmdId}/kill`,
      method: "POST",
      query: query,
      format: "json",
      ...params,
    });
  /**
   * No description
   *
   * @tags SandboxesService
   * @name SandboxesServiceGetSandboxCommandLogs
   * @request GET:/v1/core/sandboxes/{id}/commands/{cmdId}/logs
   */
  sandboxesServiceGetSandboxCommandLogs = (
    id: string,
    cmdId: string,
    query?: {
      organizationId?: string;
    },
    params: RequestParams = {},
  ) =>
    this.request<V1GetSandboxCommandLogsResponse, RpcStatus>({
      path: `/v1/core/sandboxes/${id}/commands/${cmdId}/logs`,
      method: "GET",
      query: query,
      format: "json",
      ...params,
    });
  /**
   * No description
   *
   * @tags SandboxesService
   * @name SandboxesServiceCreateSandboxDirectory
   * @request POST:/v1/core/sandboxes/{id}/directories
   */
  sandboxesServiceCreateSandboxDirectory = (
    id: string,
    body: SandboxesServiceCreateSandboxDirectoryBody,
    params: RequestParams = {},
  ) =>
    this.request<V1CreateSandboxDirectoryResponse, RpcStatus>({
      path: `/v1/core/sandboxes/${id}/directories`,
      method: "POST",
      body: body,
      type: ContentType.Json,
      format: "json",
      ...params,
    });
  /**
   * No description
   *
   * @tags SandboxesService
   * @name SandboxesServiceExtendSandboxTimeout
   * @request POST:/v1/core/sandboxes/{id}/extend-timeout
   */
  sandboxesServiceExtendSandboxTimeout = (
    id: string,
    body: SandboxesServiceExtendSandboxTimeoutBody,
    params: RequestParams = {},
  ) =>
    this.request<V1ExtendSandboxTimeoutResponse, RpcStatus>({
      path: `/v1/core/sandboxes/${id}/extend-timeout`,
      method: "POST",
      body: body,
      type: ContentType.Json,
      format: "json",
      ...params,
    });
  /**
   * No description
   *
   * @tags SandboxesService
   * @name SandboxesServiceGetSandboxFile
   * @request GET:/v1/core/sandboxes/{id}/files
   */
  sandboxesServiceGetSandboxFile = (
    id: string,
    query?: {
      organizationId?: string;
      path?: string;
    },
    params: RequestParams = {},
  ) =>
    this.request<V1GetSandboxFileResponse, RpcStatus>({
      path: `/v1/core/sandboxes/${id}/files`,
      method: "GET",
      query: query,
      format: "json",
      ...params,
    });
  /**
   * No description
   *
   * @tags SandboxesService
   * @name SandboxesServiceWriteSandboxFile
   * @request POST:/v1/core/sandboxes/{id}/files
   */
  sandboxesServiceWriteSandboxFile = (
    id: string,
    body: SandboxesServiceWriteSandboxFileBody,
    params: RequestParams = {},
  ) =>
    this.request<V1WriteSandboxFileResponse, RpcStatus>({
      path: `/v1/core/sandboxes/${id}/files`,
      method: "POST",
      body: body,
      type: ContentType.Json,
      format: "json",
      ...params,
    });
  /**
   * No description
   *
   * @tags SandboxesService
   * @name SandboxesServiceCreateSandboxSnapshot
   * @request POST:/v1/core/sandboxes/{id}/snapshot
   */
  sandboxesServiceCreateSandboxSnapshot = (
    id: string,
    body: SandboxesServiceCreateSandboxSnapshotBody,
    params: RequestParams = {},
  ) =>
    this.request<V1SandboxSnapshot, RpcStatus>({
      path: `/v1/core/sandboxes/${id}/snapshot`,
      method: "POST",
      body: body,
      type: ContentType.Json,
      format: "json",
      ...params,
    });
  /**
 * No description
 *
 * @tags SandboxesService
 * @name SandboxesServiceStopSandbox
 * @summary StopSandbox stops a running sandbox. For sandboxes created with
`persistent = true`, the controlplane first captures an auto-snapshot
keyed to the sandbox id (returned in `auto_snapshot_id`) so the
sandbox can later be brought back via UpdateSandbox(resume=true)
without losing filesystem state. For non-persistent sandboxes the
server is simply stopped and no snapshot is taken.
 * @request POST:/v1/core/sandboxes/{id}/stop
 */
  sandboxesServiceStopSandbox = (
    id: string,
    body: SandboxesServiceStopSandboxBody,
    params: RequestParams = {},
  ) =>
    this.request<V1StopSandboxResponse, RpcStatus>({
      path: `/v1/core/sandboxes/${id}/stop`,
      method: "POST",
      body: body,
      type: ContentType.Json,
      format: "json",
      ...params,
    });
}
