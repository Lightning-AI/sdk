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
  SandboxesServiceExtendSandboxTimeoutBody,
  SandboxesServiceRunSandboxCommandBody,
  SandboxesServiceWriteSandboxFileBody,
  V1CreateSandboxDirectoryResponse,
  V1CreateSandboxRequest,
  V1DeleteSandboxResponse,
  V1ExtendSandboxTimeoutResponse,
  V1GetSandboxCommandLogsResponse,
  V1GetSandboxCommandResponse,
  V1GetSandboxFileResponse,
  V1KillSandboxCommandResponse,
  V1ListSandboxesResponse,
  V1RunSandboxCommandResponse,
  V1Sandbox,
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
   * @request GET:/v1/core/sandboxes
   */
  sandboxesServiceListSandboxes = (
    query?: {
      organizationId?: string;
      pageToken?: string;
      /** @format int64 */
      limit?: string;
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
}
