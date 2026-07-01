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

export interface SandboxesServiceCreateSandboxSnapshotBody {
  organizationId?: string;
  /**
   * Optional expiration in milliseconds. When unset, the platform default applies.
   * Use 0 to request no expiration.
   * @format uint64
   */
  expiration?: string;
  /** Optional tar exclude override for this snapshot. When unset, the platform default applies. */
  excludes?: string[];
  /**
   * project_id is required: snapshots are stored in the cluster bucket
   * under the project's prefix and authorization is project-scoped.
   */
  projectId?: string;
}

export interface SandboxesServiceExtendSandboxTimeoutBody {
  organizationId?: string;
  /**
   * The amount of time in milliseconds to add to the current timeout. Must be at least 1000ms (1 second).
   * @format uint64
   */
  timeout?: string;
}

export interface SandboxesServiceFinalizeSandboxSnapshotBody {
  organizationId?: string;
  /**
   * sha256 digest of the manifest body the agent just PUT to
   * object_key. Lets the controlplane verify it's actually there
   * before flipping the row to "ready".
   */
  manifestSha256?: string;
  /**
   * Total logical size of the snapshot — sum of all unique blob
   * sizes plus the manifest body. Surfaced in the row's size_bytes
   * for billing/display.
   * @format uint64
   */
  sizeBytes?: string;
  /**
   * rootfs digest the snapshot was captured against; persisted on
   * the row so restore-compatibility check doesn't have to fetch
   * and parse the manifest.
   */
  rootfsDigest?: string;
}

export interface SandboxesServiceGetSandboxSnapshotBlobDownloadUrlsBody {
  organizationId?: string;
  sha256Digests?: string[];
}

export interface SandboxesServiceGetSandboxSnapshotBlobUploadUrlsBody {
  organizationId?: string;
  /**
   * sha256 hex digests of the unique blobs the caller wants to upload.
   * The server checks each against the cluster blob store; missing
   * ones get presigned URLs returned in `upload_urls`, present ones
   * are echoed in `existing_digests` so the caller skips them.
   * Empty list rejected.
   */
  sha256Digests?: string[];
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

export interface SandboxesServiceStopSandboxBody {
  organizationId?: string;
  /**
   * Optional project the auto-snapshot is written under for persistent
   * sandboxes. When unset, the controlplane falls back to the project the
   * sandbox was originally created in (recorded on the underlying server
   * row). Ignored for non-persistent sandboxes (no snapshot is taken in
   * that case).
   */
  projectId?: string;
}

export interface SandboxesServiceUpdateSandboxBody {
  organizationId?: string;
  /**
   * When true, resume a previously stopped persistent sandbox from
   * its most recent auto-snapshot. The sandbox id is preserved. The
   * call is a no-op (returns the current Sandbox) when the sandbox
   * is already running. Returns an error when the sandbox is not
   * persistent or has no resumable auto-snapshot.
   */
  resume?: boolean;
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
  snapshotId?: string;
  /**
   * Whether the sandbox persists its state across restarts via automatic
   * snapshots. Defaults to true.
   *
   * When true, the controlplane automatically snapshots the sandbox on idle,
   * sleep, or eviction, and transparently restores it (via the FUSE
   * snapshot/restore path; see sandbox_fuse_snapshot_restore.md) the next
   * time the sandbox id is accessed. This makes the sandbox id a durable
   * handle suitable for long-lived workflow orchestration that may pause
   * across step boundaries.
   *
   * When false, the sandbox is best-effort ephemeral: state is lost on
   * stop, idle reclaim, or host reschedule.
   */
  persistent?: boolean;
  /**
   * Project the sandbox is owned by. Recommended for persistent
   * sandboxes — the controlplane needs a project to scope the
   * auto-snapshot bucket prefix on idle eviction and on later
   * StopSandbox calls without an explicit project_id. Optional for
   * non-persistent sandboxes (no auto-snapshot is taken).
   */
  projectId?: string;
  /**
   * OCI image reference for the sandbox rootfs, e.g.
   * "docker.io/library/python:3.13" or
   * "ghcr.io/org/img@sha256:...". When set, the controlplane uses this
   * image instead of the curated sandbox-<runtime> flavour. Mutually
   * exclusive with `runtime`. gVisor (CPU) sandboxes only — VM-backed
   * (GPU / InfiniBand) requests reject this field.
   */
  image?: string;
  /**
   * Name of a project-scoped Secret of type SECRET_TYPE_DOCKER_REGISTRY
   * the controlplane resolves to pull credentials for `image`. Same
   * mechanism as JobSpec.image_secret_ref. Only valid when `image` is
   * set; empty + `image` set = anonymous public-registry pull.
   */
  imageSecretRef?: string;
}

export type V1DeleteSandboxResponse = object;

export type V1DeleteSandboxSnapshotResponse = object;

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

export interface V1GetSandboxResourceMetricsResponse {
  samples?: V1SandboxResourceMetricSample[];
}

export interface V1GetSandboxSnapshotBlobDownloadUrlsResponse {
  downloadUrls?: V1SandboxSnapshotBlobDownloadUrl[];
}

export interface V1GetSandboxSnapshotBlobUploadUrlsResponse {
  /** Presigned PUT URL per blob the caller still needs to upload. */
  uploadUrls?: V1SandboxSnapshotBlobUploadUrl[];
  /**
   * sha256 digests already present in the cluster bucket. Caller
   * skips upload for these.
   */
  existingDigests?: string[];
}

export type V1KillSandboxCommandResponse = object;

export interface V1ListSandboxCommandsResponse {
  commands?: V1SandboxCommand[];
}

export interface V1ListSandboxSnapshotsResponse {
  snapshots?: V1SandboxSnapshot[];
  nextPageToken?: string;
  previousPageToken?: string;
  /** @format int64 */
  totalSize?: string;
}

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
  /** @format date-time */
  createdAt?: string;
}

export interface V1Sandbox {
  id?: string;
  name?: string;
  organizationId?: string;
  clusterId?: string;
  instanceType?: string;
  spot?: boolean;
  /**
   * Lifecycle status of the sandbox. In addition to the underlying
   * server states (running, stopping, stopped, error, ...) the
   * controlplane surfaces:
   *   - "paused":  the sandbox is a persistent sandbox whose server
   *                row no longer exists, but whose auto-snapshot does.
   *                ListSandboxes and GetSandbox synthesise a Sandbox
   *                from the most recent auto-snapshot so the sandbox
   *                id keeps appearing in user-facing surfaces while it
   *                is hibernated. Resume via UpdateSandbox(resume=true).
   */
  status?: string;
  cloudspaceId?: string;
  ports?: string[];
  runtime?: string;
  /** @format date-time */
  createdAt?: string;
  /** @format date-time */
  updatedAt?: string;
  /**
   * Mirrors CreateSandboxRequest.persistent. Reflects the durability
   * setting the sandbox was created with. See
   * sandbox_fuse_snapshot_restore.md for the lifecycle.
   */
  persistent?: boolean;
  /**
   * Project the sandbox belongs to. Mirrors CreateSandboxRequest.project_id
   * captured onto Server.Metadata.ProjectId at create time, surfaced here
   * so list/get callers (UI, SDK) can group sandboxes per teamspace
   * without joining against the underlying server row. Empty for
   * sandboxes created before this field landed and for sandboxes whose
   * create request omitted project_id.
   */
  projectId?: string;
  /**
   * Per-phase wall-clock breakdown of the create flow, combining the
   * controlplane's own stopwatch (`cp.*` phases) with the agent's
   * litvisor-side breakdown (`agent.*` phases). Populated only on the
   * CreateSandbox response and only when the requesting user is
   * internal (`user.details.internal=true`); always empty otherwise
   * and always empty on List/Get. Used to answer "where did the time
   * go" without scraping Prometheus or correlating logs across hops.
   */
  phaseDurations?: V1SandboxPhaseDuration[];
  /**
   * User who created the sandbox. Mirrors Server.Spec.UserId stamped at
   * create time. Empty for sandboxes created before this field landed.
   */
  userId?: string;
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
  /**
   * Source snapshot used to create this sandbox, when it was restored from
   * a snapshot. Mirrors CreateSandboxRequest.snapshot_id.
   */
  snapshotId?: string;
  /**
   * OCI image reference for the sandbox rootfs, e.g.
   * "docker.io/library/python:3.13" or
   * "ghcr.io/org/img@sha256:...". When set, the controlplane uses this
   * image instead of the curated sandbox-<runtime> flavour. Mutually
   * exclusive with `runtime`. gVisor (CPU) sandboxes only — VM-backed
   * (GPU / InfiniBand) requests reject this field.
   */
  image?: string;
  /**
   * Name of a project-scoped Secret of type SECRET_TYPE_DOCKER_REGISTRY
   * the controlplane resolves to pull credentials for `image`. Same
   * mechanism as JobSpec.image_secret_ref. Only valid when `image` is
   * set; empty + `image` set = anonymous public-registry pull.
   */
  imageSecretRef?: string;
  /**
   * Cluster machine the sandbox is (or was last) placed on. Returned on
   * create/get/list, but — like phase_durations — only to internal
   * Lightning users (`user.details.internal=true`); always empty for
   * external callers and for sandboxes created before this field landed.
   * Used to attribute sandbox performance to specific hosts.
   */
  machineId?: string;
  /**
   * Public HTTPS URLs for the sandbox's user-exposed `ports`, keyed by the
   * port number as a string (e.g. "8080" -> "https://8080-<id>-s.cloudspaces.litng.ai").
   * Each URL routes through the cluster proxy to that port inside the sandbox.
   * Only the ports the caller requested at create time are included; the
   * internal sandbox API port is never exposed. Populated on create / get /
   * list / update responses; empty when the sandbox has no user ports.
   */
  portUrls?: Record<string, string>;
}

export interface V1SandboxCommand {
  id?: string;
  command?: string;
  output?: string;
  /** @format int32 */
  exitCode?: number;
  running?: boolean;
  /** @format date-time */
  createdAt?: string;
  /** @format date-time */
  updatedAt?: string;
}

/** Per-phase wall-clock duration captured by the litvisor controller. */
export interface V1SandboxPhaseDuration {
  phase?: string;
  /** @format int64 */
  durationMs?: string;
}

/** One downsampled CPU/memory sample for a sandbox. */
export interface V1SandboxResourceMetricSample {
  /** @format date-time */
  timestamp?: string;
  /**
   * Average CPU utilization across the bucket, 0-100.
   * @format float
   */
  cpuPercentage?: number;
  /**
   * Average memory utilization across the bucket, 0-100.
   * @format float
   */
  memoryPercentage?: number;
  /** @format int64 */
  numCpus?: number;
  /** @format uint64 */
  memoryUsedBytes?: string;
  /** @format uint64 */
  memoryLimitBytes?: string;
}

export interface V1SandboxSnapshot {
  id?: string;
  organizationId?: string;
  projectId?: string;
  sourceSandboxId?: string;
  /**
   * status transitions on the controlplane:
   *   - "saving": row created, agent capture + S3 upload in progress.
   *   - "ready":  tarball lives in object storage; restorable.
   *   - "failed": capture or upload failed; not restorable.
   * Only "ready" snapshots may be used to create a new sandbox.
   */
  status?: string;
  /** @format uint64 */
  sizeBytes?: string;
  /** @format date-time */
  createdAt?: string;
  /** @format date-time */
  updatedAt?: string;
  /** @format date-time */
  expiresAt?: string;
  runtime?: string;
  runtimeImage?: string;
  rootfsDigest?: string;
  tarExcludes?: string[];
  /**
   * True when this snapshot was auto-captured by the controlplane
   * because its source sandbox was created with `persistent = true`
   * and was stopped (via StopSandbox or idle/eviction). Auto-snapshots
   * represent the durable state of a paused persistent sandbox: one
   * current auto-snapshot per sandbox id, rotated in place on each
   * capture. A persistent sandbox is resumed from its auto-snapshot
   * via UpdateSandbox(resume=true), which preserves the sandbox id.
   *
   * User-initiated snapshots created via CreateSandboxSnapshot have
   * this field set to false, and `source_sandbox_id` may point at a
   * sandbox that has since been deleted.
   */
  sourceSandboxPersistent?: boolean;
  /**
   * The source sandbox's instance type at capture time, in the form
   * the controlplane persisted on `Server.Spec.InstanceType` (i.e. the
   * post-translation sandbox-pool slug such as "cpu-sandbox-4").
   * Replayed verbatim by UpdateSandbox(resume=true) so the resumed
   * sandbox comes back with the same CPU / memory / disk shape as the
   * original. Best-effort: empty for snapshots captured before this
   * field landed; the resume path then falls back to a default.
   */
  sourceSandboxInstanceType?: string;
  /**
   * The source sandbox's user-facing name (CreateSandboxRequest.name)
   * at capture time. Surfaced back via ListSandboxes / GetSandbox for
   * paused persistent sandboxes so the original name keeps appearing
   * while the sandbox is hibernated, and reused by UpdateSandbox(
   * resume=true) so the resumed sandbox keeps its identity instead of
   * regressing to a synthetic placeholder. Best-effort: empty for
   * snapshots captured before this field landed.
   */
  sourceSandboxName?: string;
  /**
   * Outbound network policy captured from the source sandbox at snapshot
   * time. Replayed by UpdateSandbox(resume=true) so a paused persistent
   * sandbox keeps the same egress restrictions after resume. Best-effort:
   * unset for snapshots captured before this field landed; the resume
   * path then treats missing policy as allow-all.
   */
  sourceSandboxNetworkPolicy?: V1NetworkPolicy;
}

/**
 * SandboxSnapshotBlobDownloadUrl pairs a sha256 with its presigned GET
 * URL. One per requested digest, in request order.
 */
export interface V1SandboxSnapshotBlobDownloadUrl {
  sha256?: string;
  url?: string;
}

/**
 * SandboxSnapshotBlobUploadUrl pairs a sha256 digest with the presigned
 * PUT URL the agent uses to push that blob. Digests are echoed back so
 * the agent doesn't need to maintain its own index-to-URL mapping when
 * it issues a batched request.
 */
export interface V1SandboxSnapshotBlobUploadUrl {
  sha256?: string;
  url?: string;
}

export interface V1StopSandboxResponse {
  /**
   * For sandboxes created with `persistent = true`, the id of the
   * auto-snapshot the controlplane captured before stopping the
   * server. Subsequent UpdateSandbox(resume=true) calls against the
   * sandbox id will resume from this snapshot. Empty when the
   * sandbox is non-persistent (no snapshot is taken in that case).
   */
  autoSnapshotId?: string;
}

export type V1WriteSandboxFileResponse = object;
