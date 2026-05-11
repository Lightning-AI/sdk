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

export interface SandboxesServiceCreateSandboxDirectoryBody {
  organizationId?: string;
  path?: string;
}

export interface SandboxesServiceExtendSandboxTimeoutBody {
  organizationId?: string;
  /**
   * The amount of time in milliseconds to add to the current timeout. Must be at least 1000ms (1 second).
   * @format uint64
   */
  timeout?: string;
}

export interface SandboxesServiceRunSandboxCommandBody {
  organizationId?: string;
  command?: string;
  detached?: boolean;
  args?: string[];
  cwd?: string;
  env?: Record<string, string>;
  sudo?: boolean;
}

export interface SandboxesServiceWriteSandboxFileBody {
  organizationId?: string;
  path?: string;
  content?: string;
}

/**
 * `Any` contains an arbitrary serialized protocol buffer message along with a
 * URL that describes the type of the serialized message.
 *
 * Protobuf library provides support to pack/unpack Any values in the form
 * of utility functions or additional generated methods of the Any type.
 *
 * Example 1: Pack and unpack a message in C++.
 *
 *     Foo foo = ...;
 *     Any any;
 *     any.PackFrom(foo);
 *     ...
 *     if (any.UnpackTo(&foo)) {
 *       ...
 *     }
 *
 * Example 2: Pack and unpack a message in Java.
 *
 *     Foo foo = ...;
 *     Any any = Any.pack(foo);
 *     ...
 *     if (any.is(Foo.class)) {
 *       foo = any.unpack(Foo.class);
 *     }
 *
 * Example 3: Pack and unpack a message in Python.
 *
 *     foo = Foo(...)
 *     any = Any()
 *     any.Pack(foo)
 *     ...
 *     if any.Is(Foo.DESCRIPTOR):
 *       any.Unpack(foo)
 *       ...
 *
 * Example 4: Pack and unpack a message in Go
 *
 *      foo := &pb.Foo{...}
 *      any, err := anypb.New(foo)
 *      if err != nil {
 *        ...
 *      }
 *      ...
 *      foo := &pb.Foo{}
 *      if err := any.UnmarshalTo(foo); err != nil {
 *        ...
 *      }
 *
 * The pack methods provided by protobuf library will by default use
 * 'type.googleapis.com/full.type.name' as the type URL and the unpack
 * methods only use the fully qualified type name after the last '/'
 * in the type URL, for example "foo.bar.com/x/y.z" will yield type
 * name "y.z".
 *
 *
 * JSON
 *
 * The JSON representation of an `Any` value uses the regular
 * representation of the deserialized, embedded message, with an
 * additional field `@type` which contains the type URL. Example:
 *
 *     package google.profile;
 *     message Person {
 *       string first_name = 1;
 *       string last_name = 2;
 *     }
 *
 *     {
 *       "@type": "type.googleapis.com/google.profile.Person",
 *       "firstName": <string>,
 *       "lastName": <string>
 *     }
 *
 * If the embedded message type is well-known and has a custom JSON
 * representation, that representation will be embedded adding a field
 * `value` which holds the custom JSON in addition to the `@type`
 * field. Example (for message [google.protobuf.Duration][]):
 *
 *     {
 *       "@type": "type.googleapis.com/google.protobuf.Duration",
 *       "value": "1.212s"
 *     }
 */
export interface ProtobufAny {
  /**
   * A URL/resource name that uniquely identifies the type of the serialized
   * protocol buffer message. This string must contain at least
   * one "/" character. The last segment of the URL's path must represent
   * the fully qualified name of the type (as in
   * `path/google.protobuf.Duration`). The name should be in a canonical form
   * (e.g., leading "." is not accepted).
   *
   * In practice, teams usually precompile into the binary all types that they
   * expect it to use in the context of Any. However, for URLs which use the
   * scheme `http`, `https`, or no scheme, one can optionally set up a type
   * server that maps type URLs to message definitions as follows:
   *
   * * If no scheme is provided, `https` is assumed.
   * * An HTTP GET on the URL must yield a [google.protobuf.Type][]
   *   value in binary format, or produce an error.
   * * Applications are allowed to cache lookup results based on the
   *   URL, or have them precompiled into a binary to avoid any
   *   lookup. Therefore, binary compatibility needs to be preserved
   *   on changes to types. (Use versioned type names to manage
   *   breaking changes.)
   *
   * Note: this functionality is not currently available in the official
   * protobuf release, and it is not used for type URLs beginning with
   * type.googleapis.com.
   *
   * Schemes other than `http`, `https` (or the empty scheme) might be
   * used with implementation specific semantics.
   */
  "@type"?: string;
  [key: string]: any;
}

/**
 * The `Status` type defines a logical error model that is suitable for
 * different programming environments, including REST APIs and RPC APIs. It is
 * used by [gRPC](https://github.com/grpc). Each `Status` message contains
 * three pieces of data: error code, error message, and error details.
 *
 * You can find out more about this error model and how to work with it in the
 * [API Design Guide](https://cloud.google.com/apis/design/errors).
 */
export interface RpcStatus {
  /**
   * The status code, which should be an enum value of [google.rpc.Code][google.rpc.Code].
   * @format int32
   */
  code?: number;
  /**
   * A developer-facing error message, which should be in English. Any
   * user-facing error message should be localized and sent in the
   * [google.rpc.Status.details][google.rpc.Status.details] field, or localized by the client.
   */
  message?: string;
  /**
   * A list of messages that carry the error details.  There is a common set of
   * message types for APIs to use.
   */
  details?: ProtobufAny[];
}

export type V1CreateSandboxDirectoryResponse = object;

export interface V1CreateSandboxRequest {
  name?: string;
  organizationId?: string;
  clusterId?: string;
  instanceType?: string;
  spot?: boolean;
  cloudspaceId?: string;
  runtime?: string;
  ports?: string[];
  /**
   * Optional override for the sandbox's writable disk size, in GB. When
   * unset (0) the sandbox inherits the instance-type default from the
   * `cpu-sandbox-*` accelerator (10 / 40 / 60 / 80 GB for cpu-2/4/8/16).
   * Only applies to CPU sandboxes — GPU / VM paths ignore this field.
   * @format uint64
   */
  storageGb?: string;
  /**
   * Maximum duration in milliseconds that the sandbox can run before being automatically stopped.
   * @format uint64
   */
  timeout?: string;
  /**
   * Network access policy for the sandbox. Controls which external hosts the
   * sandbox can communicate with. When unset, the sandbox inherits the default
   * network policy.
   */
  networkPolicy?: V1NetworkPolicy;
}

export type V1DeleteSandboxResponse = object;

export type V1ExtendSandboxTimeoutResponse = object;

export interface V1GetSandboxCommandLogsResponse {
  logs?: V1LogMessage[];
  followUrl?: string;
}

export interface V1GetSandboxCommandResponse {
  output?: string;
  /** @format int32 */
  exitCode?: number;
  running?: boolean;
}

export interface V1GetSandboxFileResponse {
  content?: string;
}

export type V1KillSandboxCommandResponse = object;

export interface V1ListSandboxesResponse {
  sandboxes?: V1Sandbox[];
  nextPageToken?: string;
  previousPageToken?: string;
  /** @format int64 */
  totalSize?: string;
}

export interface V1LogMessage {
  timestamp?: string;
  message?: string;
}

/** NetworkPolicy controls outbound network access for a sandbox. */
export interface V1NetworkPolicy {
  /**
   * The network access policy mode.
   * - "allow-all": permit all outbound traffic.
   * - "deny-all": block all outbound traffic.
   * - "custom": specify explicit allow/deny rules via the fields below.
   * - "default-allow": allow all traffic except for explicit deny rules.
   * - "default-deny": deny all traffic except for explicit allow rules.
   */
  mode?: string;
  /**
   * List of domain names the sandbox is allowed to connect to. Only applies
   * when mode is "custom". Supports wildcard patterns (e.g., "*.example.com"
   * matches all subdomains).
   */
  allowedDomains?: string[];
  /**
   * List of IP address ranges (in CIDR notation) the sandbox is allowed to
   * connect to. Traffic to these addresses bypasses domain-based restrictions.
   */
  allowedCidrs?: string[];
  /**
   * List of IP address ranges (in CIDR notation) the sandbox is blocked from
   * connecting to. These rules take precedence over all allowed rules.
   */
  deniedCidrs?: string[];
}

export interface V1RunSandboxCommandResponse {
  cmdId?: string;
  output?: string;
  /** @format int32 */
  exitCode?: number;
}

export interface V1Sandbox {
  id?: string;
  name?: string;
  organizationId?: string;
  clusterId?: string;
  instanceType?: string;
  spot?: boolean;
  status?: string;
  cloudspaceId?: string;
  ports?: string[];
  runtime?: string;
  /** @format date-time */
  createdAt?: string;
  /** @format date-time */
  updatedAt?: string;
}

export type V1WriteSandboxFileResponse = object;
