---
title: Slack Collaboration Control Plane V1
summary: Add a Slack-first collaboration control plane for roles, spaces, memory scopes, handoffs, schedules, and approvals.
read_when:
  - Planning or implementing Slack collaboration beyond the current agents and bindings surfaces
  - Deciding how role routing, memory isolation, and bot handoffs should work in Slack
  - Reviewing rollout, validation, or explain mode behavior for collaboration managed Slack surfaces
---

# Slack Collaboration Control Plane V1

## Status

Proposed.

This document defines the `collaboration` control plane that should exist before
OpenClaw claims to support a complete Slack collaboration system with:

- role aware routing
- private and shared memory boundaries
- structured bot handoffs
- role and space targeted schedules
- role aware approvals

The current mainline codebase has pieces of this behavior across agents,
bindings, Slack channel config, memory search, and cron delivery, but not a
single first class control plane that makes the system coherent.

## Problem

The current configuration surfaces are sufficient for isolated capabilities, but
not for a complete Slack collaboration model.

Today:

- `agents` defines execution units.
- `bindings` and channel config define route entry points.
- Slack config defines allowlists, tool filters, and transport behavior.
- memory config defines storage and search primitives.
- cron config defines time based delivery.

What is missing is the business layer that answers:

- which Slack user maps to which business identity
- which role owns a Slack thread
- when one bot may hand off to another
- which memory scopes may be read or published in a given space
- which scheduled summaries are allowed to read which data
- which roles may approve high risk actions

Without this layer, users must encode collaboration policy indirectly through
unrelated config surfaces. That leads to fragile behavior, duplicated intent,
and no reliable explain mode.

## Goals

- Add a first class `collaboration` control plane for Slack collaboration.
- Model business roles independently from Slack native permissions.
- Separate agent runtime identity from Slack display identity.
- Make memory isolation the default and shared memory explicit.
- Support structured bot handoffs without bot message loops.
- Support schedules targeted at an identity, role, or space instead of only a
  raw channel id.
- Support role aware approval policy.
- Provide deterministic validation, explain output, and audit events.
- Roll out safely through `shadow` mode before enforcement.

## Non Goals

- No cross channel collaboration model in V1.
- No automatic mapping from Slack admin or member state to business roles.
- No freeform ABAC or policy DSL in V1.
- No automatic broadcast where multiple bots respond to the same Slack message
  by default.
- No replacement of the existing `agents`, `channels.slack.accounts`, `cron`,
  or memory runtime surfaces.
- No migration of unmanaged Slack surfaces to the collaboration model.

## Design Principles

### Business roles are OpenClaw concepts

Roles such as `ceo`, `product`, and `ops` are application level concepts. They
must not be inferred from Slack workspace roles.

### Agent, bot identity, and memory scope are separate

An `agent` is the runtime executor. A `bot` is the Slack facing identity. A
memory scope is the data boundary. These must not be collapsed into a single
object.

### Isolation is the default

Private memory is the default write target. Moving information into
`role_shared` or `space_shared` requires an explicit publish step.

### Collaboration must be structured

Bot collaboration should be represented as an internal `handoff` contract, not
as raw bot authored messages that trigger each other.

### Collaboration decisions must be explainable

Every collaboration managed message should have a deterministic answer for:

- who the actor is
- which space it belongs to
- which role owns the thread
- which memory scopes are readable
- why a handoff or approval was allowed or denied

## V1 Scope

V1 is intentionally narrow:

- Slack only
- three memory scopes:
  - `private`
  - `role_shared`
  - `space_shared`
- three collaboration space kinds:
  - `dm`
  - `role`
  - `project`
- explicit handoffs only
- role based approvals only
- collaboration managed schedules compiled into the existing cron runtime

## Source Of Truth

`collaboration` becomes the source of truth for collaboration policy.

Existing runtime surfaces remain in place:

- `agents` continues to define runtime execution units
- `channels.slack.accounts` continues to define Slack transport credentials and
  account level connectivity
- memory runtime continues to provide storage and search
- cron continues to provide scheduling and delivery execution
- approvals runtime continues to provide approval transport and decision
  persistence

`collaboration` does not replace those systems. It overlays policy and compiles
to them.

## Managed Surfaces

A Slack surface is collaboration managed when it is referenced by one of:

- `collaboration.spaces.<spaceId>.slack.channels`
- `collaboration.spaces.<spaceId>.slack.users`

Rules:

- managed surfaces use collaboration routing and policy
- unmanaged surfaces continue to use existing routing behavior
- on managed surfaces, collaboration policy wins over overlapping manual
  `bindings` or Slack channel rules
- on unmanaged surfaces, existing config continues to win

## Control Plane Shape

The proposed top level shape is:

```ts
type CollaborationConfig = {
  version: 1;
  mode?: "disabled" | "shadow" | "enforced";
  identities: CollaborationIdentitiesConfig;
  bots: Record<BotId, CollaborationBotConfig>;
  roles: Record<RoleId, CollaborationRoleConfig>;
  spaces: Record<SpaceId, CollaborationSpaceConfig>;
  memory?: CollaborationMemoryConfig;
  routing?: CollaborationRoutingConfig;
  schedules?: CollaborationSchedulesConfig;
  approvals?: CollaborationApprovalConfig;
  audit?: CollaborationAuditConfig;
};
```

### Mode

- `disabled`: collaboration is ignored
- `shadow`: collaboration computes decisions but does not take over runtime
  behavior
- `enforced`: collaboration decisions take effect on managed surfaces

Default: `enforced`

## Core Objects

### Identity

An identity represents a human actor known to the collaboration system.

```ts
type CollaborationIdentitiesConfig = {
  users: Record<SlackUserId, CollaborationIdentityBinding>;
};

type CollaborationIdentityBinding = {
  identityId: IdentityId;
  displayName?: string;
  roles: RoleId[];
  defaultRole?: RoleId;
  scheduleDelivery?: {
    preferDm?: boolean;
    fallbackBotId?: BotId;
  };
};
```

Rules:

- every Slack user binding must resolve to at least one role
- `defaultRole` must be one of `roles`
- if `defaultRole` is omitted, use `roles[0]`

### Bot

A bot maps a Slack facing identity to a runtime agent and a role.

```ts
type CollaborationBotConfig = {
  slackAccountId: string;
  agentId: string;
  role: RoleId;
  displayName?: string;
  identityStyle?: "role" | "agent";
  allowedSpaces?: SpaceId[];
  canInitiateHandoffs?: boolean;
  canReceiveHandoffs?: boolean;
};
```

Rules:

- `slackAccountId` must exist in `channels.slack.accounts`
- `agentId` must exist in `agents`
- `role` must exist in `collaboration.roles`

### Role

A role defines default ownership, permissions, and memory policy.

```ts
type CollaborationRoleConfig = {
  defaultAgentId: string;
  defaultBotId: BotId;
  permissions: CollaborationPermission[];
  memoryPolicy?: {
    defaultWriteScope?: "private" | "role_shared" | "space_shared";
    readableScopes?: Array<"private" | "role_shared" | "space_shared">;
    publishableScopes?: Array<"role_shared" | "space_shared">;
  };
  schedulePolicy?: {
    canCreate?: boolean;
    canEdit?: boolean;
    canDelete?: boolean;
    allowedAudienceKinds?: Array<"identity" | "role" | "space">;
    allowPrivateDigest?: boolean;
  };
};
```

Permissions in V1:

- `memory.read.private`
- `memory.read.role_shared`
- `memory.read.space_shared`
- `memory.write.private`
- `memory.publish.role_shared`
- `memory.publish.space_shared`
- `schedule.read`
- `schedule.create`
- `schedule.edit`
- `schedule.delete`
- `agent.handoff`
- `agent.mention`
- `exec.approve`
- `config.edit`

### Space

A space defines the collaboration boundary that a Slack thread belongs to.

```ts
type CollaborationSpaceConfig = {
  kind: "dm" | "role" | "project";
  displayName?: string;
  ownerRole?: RoleId;
  memberRoles?: RoleId[];
  slack?: {
    channels?: SlackChannelId[];
    users?: SlackUserId[];
    requireMention?: boolean;
    replyThreadMode?: "owner" | "free" | "strict_owner";
    allowBotMessages?: "none" | "handoff_only";
  };
  memory?: {
    sharedScopeId?: string;
    readableByRoles?: RoleId[];
    writableByRoles?: RoleId[];
    publishRequires?: CollaborationPermission[];
  };
  handoffs?: {
    allowedTargets?: RoleId[];
    requireExplicitMention?: boolean;
    maxDepth?: number;
  };
  schedules?: {
    allowed?: boolean;
    defaultDestinations?: CollaborationDeliveryTarget[];
    quietHours?: {
      tz: string;
      start: string;
      end: string;
    };
  };
};
```

Rules:

- `project` and `role` spaces must define `ownerRole`
- `memberRoles` must include `ownerRole`
- `dm` spaces must define at least one Slack user
- `allowBotMessages` may only be `none` or `handoff_only`

### Memory

V1 memory scopes:

- `private`
- `role_shared`
- `space_shared`

Global memory policy:

```ts
type CollaborationMemoryConfig = {
  scopes?: {
    private?: { default?: boolean };
    role_shared?: { partitionBy: "role" };
    space_shared?: { partitionBy: "space" };
  };
  rules?: {
    requireProvenance?: boolean;
    requireExplicitPublish?: boolean;
    denyGlobalSearchByDefault?: boolean;
  };
};
```

### Routing

Routing defines how OpenClaw picks the owner role and how explicit mentions
become handoffs.

```ts
type CollaborationRoutingConfig = {
  ownerSelection?: {
    dm?: "identity_default_role";
    role?: "space_owner_role";
    project?: "space_owner_role";
  };
  mentionRouting?: {
    explicitAgentMention?: boolean;
    fallbackToOwner?: boolean;
  };
  handoff?: {
    mode?: "structured";
    dedupeWindow?: string;
    maxDepth?: number;
    allowBotAuthoredReentry?: boolean;
  };
};
```

### Schedules

Schedules are collaboration level intents that compile into the cron runtime.

```ts
type CollaborationSchedulesConfig = {
  jobs: CollaborationScheduleJob[];
};

type CollaborationScheduleJob = {
  id: string;
  enabled?: boolean;
  audience:
    | { kind: "identity"; id: IdentityId }
    | { kind: "role"; id: RoleId }
    | { kind: "space"; id: SpaceId };
  sourceSpaces: SpaceId[];
  at?: string;
  every?: string;
  cron?: string;
  tz?: string;
  delivery: CollaborationDeliveryTarget[];
  memoryReadScopes?: Array<"private" | "role_shared" | "space_shared">;
  template?: string;
  systemPrompt?: string;
  ownerRole?: RoleId;
};
```

### Approvals

Approvals define which roles may approve high risk actions.

```ts
type CollaborationApprovalConfig = {
  policies: Record<string, CollaborationApprovalPolicy>;
};

type CollaborationApprovalPolicy = {
  when: string[];
  approverRoles: RoleId[];
  delivery: Array<"dm" | "origin_thread">;
  visibility?: "summary_only" | "full_context";
  agentFilter?: string[];
  spaceFilter?: SpaceId[];
};
```

### Audit

Audit defines explainability and event retention behavior.

```ts
type CollaborationAuditConfig = {
  enabled?: boolean;
  retainDays?: number;
  redactBodies?: boolean;
  explainMode?: boolean;
};
```

## Owner Routing Rules

For collaboration managed Slack surfaces:

- Slack DM resolves to the sender identity default role
- role space resolves to the space owner role
- project space resolves to the space owner role

That owner role maps to:

- a default agent
- a default bot
- a default permission set
- a default memory policy

V1 rule: each inbound Slack thread has one owner agent.

Explicit mentions do not create free broadcast. They create a structured
handoff request if the target role is allowed in the current space.

## Handoff Contract

V1 collaboration between bots is explicit only.

A handoff request must include:

- `correlationId`
- `sourceSpaceId`
- `sourceSlackChannelId`
- `sourceSlackThreadTs`
- `sourceIdentityId`
- `sourceRole`
- `targetRole`
- `taskSummary`
- `allowedMemoryScopes`

Rules:

- the caller must have `agent.handoff`
- the target role must be in `space.handoffs.allowedTargets`
- the handoff depth must not exceed `maxDepth`
- child runs do not take ownership of the thread
- child runs may reply in the same thread
- ordinary bot authored Slack messages do not reenter routing

This avoids loops, duplicate replies, and implicit privilege escalation.

## Memory Semantics

### Private

`private` memory is the default write target.

It is partitioned by the acting identity and effective role. It must not be
searchable by unrelated roles.

### Role Shared

`role_shared` memory is visible within the same role unless additional policy
permits broader reads.

Typical uses:

- runbooks for `ops`
- product planning notes for `product`
- executive summaries for `ceo`

### Space Shared

`space_shared` memory is scoped to a collaboration space, typically a project.

Typical uses:

- a shared project decision
- a project summary meant for multiple roles
- a handoff artifact that should remain visible in the project context

### Publish Rule

Memory does not become shared automatically.

Publishing from `private` into `role_shared` or `space_shared` must:

- validate publish permission
- validate the target scope is allowed in the current role and space
- attach provenance metadata

Required provenance:

- actor identity id
- actor role
- agent id
- source space id
- source Slack channel id
- source Slack thread ts
- source message reference
- published at timestamp

## Schedule Semantics

Schedules are defined in collaboration space, then compiled to the existing cron
runtime as virtual jobs.

V1 requirements:

- a schedule targets an identity, role, or space
- a schedule defines one or more source spaces
- a schedule declares which memory scopes it may read
- `private` schedule reads are allowed only for identity targeted schedules when
  role policy explicitly permits that behavior
- delivery may target:
  - Slack DM
  - Slack channel
  - a space default destination

V1 rule: collaboration schedules are not directly edited through the generic
cron store. They should appear as collaboration sourced virtual jobs.

## Approval Semantics

Approval decisions stay inside OpenClaw policy, even when approval prompts are
delivered through Slack.

Rules:

- an approval policy matches an action
- matching policy resolves approver roles
- approver roles resolve to identities
- only those identities may approve or deny
- Slack delivery surface does not determine approval authority

This keeps business approval logic independent from channel membership.

## Explain And Audit

Every collaboration managed decision should be inspectable.

### Explain Output

Collaboration explain output should include:

- surface
- identity
- space
- owner route
- granted and denied permissions
- readable memory scopes
- writable and publishable scopes
- handoff policy
- delivery policy
- warnings

Representative shape:

```json
{
  "ok": true,
  "mode": "shadow",
  "surface": {
    "provider": "slack",
    "accountId": "product",
    "channelId": "C111PROJ01",
    "threadTs": "1713891000.123456",
    "senderUserId": "U111PM001"
  },
  "identity": {
    "identityId": "alice",
    "roles": ["product"],
    "defaultRole": "product",
    "effectiveRole": "product"
  },
  "space": {
    "spaceId": "project_main",
    "kind": "project"
  },
  "route": {
    "ownerRole": "product",
    "ownerAgentId": "product",
    "ownerBotId": "product_bot",
    "reason": "space_owner_role"
  },
  "permissions": {
    "granted": ["memory.read.private", "agent.handoff"],
    "denied": ["config.edit"]
  },
  "memory": {
    "readableScopes": ["private", "role_shared", "space_shared"],
    "writeDefaultScope": "private",
    "publishableScopes": ["role_shared", "space_shared"]
  }
}
```

### Audit Events

V1 must emit audit events for:

- `message.received`
- `identity.resolved`
- `space.resolved`
- `route.resolved`
- `memory.read`
- `memory.publish`
- `handoff.requested`
- `handoff.accepted`
- `handoff.rejected`
- `schedule.triggered`
- `schedule.delivered`
- `schedule.failed`
- `approval.requested`
- `approval.approved`
- `approval.denied`

Each event should carry:

- actor identity
- actor role
- agent id
- space id
- Slack surface identifiers
- decision result
- reason code
- memory scopes read or written

## Validation And Error Model

V1 should use explicit error codes, not freeform strings.

Recommended families:

- `COLLAB_SCHEMA_*`
- `COLLAB_REF_*`
- `COLLAB_POLICY_*`
- `COLLAB_RUNTIME_*`

Examples:

- `COLLAB_SCHEMA_VERSION_UNSUPPORTED`
- `COLLAB_SCHEMA_REQUIRED_FIELD_MISSING`
- `COLLAB_REF_AGENT_NOT_FOUND`
- `COLLAB_REF_SLACK_ACCOUNT_NOT_FOUND`
- `COLLAB_POLICY_DEFAULT_ROLE_NOT_IN_ROLES`
- `COLLAB_POLICY_OWNER_ROLE_NOT_MEMBER`
- `COLLAB_POLICY_HANDOFF_TARGET_OUTSIDE_SPACE`
- `COLLAB_POLICY_PRIVATE_SCOPE_NOT_ALLOWED_FOR_AUDIENCE`
- `COLLAB_RUNTIME_IDENTITY_UNRESOLVED`
- `COLLAB_RUNTIME_SPACE_UNRESOLVED`
- `COLLAB_RUNTIME_HANDOFF_DENIED`

Errors should always point to the failing path and offer a corrective hint.

## Rollout

### Phase 0

Schema only.

Deliverables:

- types
- Zod schema
- config validation
- explain only CLI surface

No runtime behavior changes.

### Phase 1

`shadow` mode on managed Slack surfaces.

Deliverables:

- managed surface detection
- collaboration explain output
- audit events
- diff between legacy route and collaboration route

Legacy routing still wins.

### Phase 2

Enforced owner routing on managed Slack surfaces.

Deliverables:

- owner route takeover
- explicit mention to handoff translation
- handoff gating

Memory gates and schedules may remain partially shadowed at this stage.

### Phase 3

Memory and schedule enforcement.

Deliverables:

- readable scope gate
- publish contract
- collaboration sourced virtual schedules

### Phase 4

Approval policy enforcement and cleanup.

Deliverables:

- role aware approval resolution
- conflict warnings for overlapping legacy config
- operator guidance for removing redundant manual config

## Implementation Plan

The first implementation slice should not attempt the full feature set at once.

### PR 1

Config surface.

- add `src/config/types.collaboration.ts`
- add `src/config/zod-schema.collaboration.ts`
- wire `collaboration` into top level config types and schema
- add validation and error codes

### PR 2

Explain and validate CLI.

- add collaboration CLI entrypoint
- add `validate`
- add `explain`

### PR 3

Slack shadow mode.

- detect collaboration managed Slack surfaces
- compute identity, space, owner route, permissions, and memory scopes
- emit explain and audit output
- do not change actual reply behavior yet

### PR 4

Enforced Slack owner routing.

- collaboration route overrides legacy route on managed surfaces
- explicit mention may trigger a handoff request when policy allows it

### PR 5

Structured handoff and memory gate.

- enforce handoff policy
- apply readable scope gate
- add publish contract

Schedules and approvals can follow after the route and memory model are stable.

## PR Cut Plan

The implementation plan above is feature oriented. This section is file
oriented and is intended for cutting the current worktree into reviewable PRs
without mixing unrelated surfaces.

### Ordering

Recommended landing order:

1. Lobster build unblock
2. collaboration config surface
3. collaboration CLI and audit readers
4. Slack managed surface routing and handoff runtime
5. collaboration memory gates and publish path
6. collaboration schedules and approval policies

The Lobster fix is not part of the collaboration control plane, but it should
land first because it removes a build blocker that otherwise obscures later
verification.

### PR 0 - Lobster build unblock

Intent:

- remove the broken `@clawdbot/lobster/core` subpath dependency
- keep the Lobster tool contract unchanged

Files:

- `extensions/lobster/src/lobster-embedded-runtime.runtime.ts`
- `extensions/lobster/src/lobster-runner.ts`
- `extensions/lobster/src/lobster-runner.test.ts`
- `extensions/lobster/README.md`
- `extensions/lobster/src/lobster-core.d.ts`

Do not mix with:

- any collaboration files
- plugin SDK baseline changes

Verification:

- `pnpm test extensions/lobster/src/lobster-runner.test.ts extensions/lobster/src/lobster-tool.test.ts extensions/lobster/src/lobster-taskflow.test.ts`
- `pnpm build`

Notes:

- if `pnpm build` still hangs in `runtime-postbuild`, record that as a separate
  blocker from the old Lobster import failure

### PR 1 - Collaboration config surface

Intent:

- introduce the `collaboration` schema and validation surface
- keep runtime behavior unchanged

Files:

- `docs/plan/slack-collaboration-control-plane-v1.md`
- `src/config/types.collaboration.ts`
- `src/config/zod-schema.collaboration.ts`
- `src/config/validation.collaboration.ts`
- `src/config/types.openclaw.ts`
- `src/config/types.ts`
- `src/config/zod-schema.ts`
- `src/config/validation.ts`
- `src/config/schema.base.generated.ts`
- `src/config/config.collaboration.test.ts`
- `docs/.generated/config-baseline.sha256`

Do not mix with:

- Slack runtime files
- memory runtime files
- cron runtime files
- plugin SDK baseline files

Verification:

- `pnpm test src/config/config.collaboration.test.ts src/config/schema.base.generated.test.ts`
- `pnpm config:schema:check`
- `pnpm config:docs:check`

Commit boundary notes:

- keep generated config baseline files in the same PR as the schema changes
- do not pull in collaboration CLI files yet

### PR 2 - Collaboration CLI and audit read path

Intent:

- add `collaboration validate`
- add `collaboration explain`
- add `collaboration audit`
- keep Slack runtime behavior unchanged

Files:

- `src/collaboration/runtime.ts`
- `src/collaboration/runtime.test.ts`
- `src/collaboration/audit.ts`
- `src/collaboration/audit.test.ts`
- `src/commands/collaboration-validate.ts`
- `src/commands/collaboration-validate.test.ts`
- `src/commands/collaboration-explain.ts`
- `src/commands/collaboration-explain.test.ts`
- `src/commands/collaboration-audit.ts`
- `src/commands/collaboration-audit.test.ts`
- `src/cli/collaboration-cli.ts`
- `src/cli/collaboration-cli.test.ts`
- `src/cli/command-catalog.ts`
- `src/cli/program/register.subclis-core.ts`
- `src/cli/program/subcli-descriptors.ts`
- `src/cli/command-startup-policy.test.ts`
- `src/cli/program/preaction.test.ts`

Do not mix with:

- `extensions/slack/**`
- `extensions/memory-core/**`
- `src/plugin-sdk/**`

Verification:

- `pnpm test src/collaboration/runtime.test.ts src/collaboration/audit.test.ts src/commands/collaboration-validate.test.ts src/commands/collaboration-explain.test.ts src/commands/collaboration-audit.test.ts src/cli/collaboration-cli.test.ts src/cli/command-startup-policy.test.ts src/cli/program/preaction.test.ts`

Commit boundary notes:

- keep CLI registration changes and the command files together
- do not include route takeover or handoff artifact files yet

### PR 3 - Slack managed surface routing and handoff runtime

Intent:

- detect managed Slack surfaces
- support shadow and enforced route selection
- add explicit handoff gating and detached handoff execution
- add handoff audit and child task linkage

Files:

- `extensions/slack/src/monitor/collaboration.runtime.ts`
- `extensions/slack/src/monitor/message-handler/prepare.ts`
- `extensions/slack/src/monitor/message-handler/dispatch.ts`
- `extensions/slack/src/monitor/message-handler/types.ts`
- `extensions/slack/src/monitor/message-handler/prepare.collaboration-shadow.test.ts`
- `extensions/slack/src/monitor/message-handler/dispatch.collaboration-handoff.test.ts`
- `src/routing/resolve-route.ts`
- `src/collaboration/handoff-artifacts.ts`
- `src/collaboration/handoff-task.ts`
- `src/collaboration/session-meta.ts`
- `src/plugin-sdk/collaboration-runtime.ts`
- `scripts/lib/plugin-sdk-entrypoints.json`
- `package.json`
- `docs/.generated/plugin-sdk-api-baseline.sha256`
- `docs/plugins/architecture.md`
- `docs/plugins/sdk-overview.md`

Do not mix with:

- memory gate implementation
- cron collaboration schedules
- Slack approval policy integration

Verification:

- `pnpm test extensions/slack/src/monitor/message-handler/prepare.test.ts extensions/slack/src/monitor/message-handler/prepare.collaboration-shadow.test.ts extensions/slack/src/monitor/message-handler/dispatch.collaboration-handoff.test.ts src/collaboration/runtime.test.ts src/commands/collaboration-explain.test.ts src/commands/collaboration-audit.test.ts`
- `pnpm plugin-sdk:api:gen`
- `pnpm plugin-sdk:api:check`

Commit boundary notes:

- the plugin SDK entrypoint and baseline drift file must stay with
  `src/plugin-sdk/collaboration-runtime.ts`
- `src/routing/resolve-route.ts` changes should be limited to new
  `matchedBy` values for collaboration sources

### PR 4 - Collaboration memory gates and publish path

Intent:

- enforce readable memory scopes
- add collaboration publish behavior
- index role shared and space shared paths

Files:

- `extensions/memory-core/index.ts`
- `extensions/memory-core/index.test.ts`
- `extensions/memory-core/src/tools.ts`
- `extensions/memory-core/src/tools.shared.ts`
- `extensions/memory-core/src/tools.test-helpers.ts`
- `extensions/memory-core/src/tools.collaboration.ts`
- `extensions/memory-core/src/tools.collaboration.test.ts`
- `extensions/memory-core/src/tools.publish.ts`
- `extensions/memory-core/src/tools.publish.test.ts`
- `extensions/memory-core/src/prompt-section.ts`
- `src/agents/memory-search.ts`
- `src/agents/memory-search.test.ts`
- `src/channels/session.ts`
- `src/channels/session.types.ts`
- `src/channels/session.test.ts`
- `src/config/sessions/store.ts`
- `src/config/sessions/types.ts`
- `src/config/sessions/store.session-key-normalization.test.ts`
- `src/memory-host-sdk/events.ts`
- `src/memory-host-sdk/host/backend-config.ts`
- `src/memory-host-sdk/host/backend-config.test.ts`
- `src/collaboration/memory-paths.ts`

Do not mix with:

- schedules and cron virtual job changes
- Slack approval policy changes

Verification:

- `pnpm test extensions/memory-core/index.test.ts extensions/memory-core/src/tools.collaboration.test.ts extensions/memory-core/src/tools.publish.test.ts extensions/memory-core/src/tools.test.ts extensions/memory-core/src/tools.citations.test.ts src/agents/memory-search.test.ts src/channels/session.test.ts src/config/sessions/store.session-key-normalization.test.ts src/memory-host-sdk/host/backend-config.test.ts`

Commit boundary notes:

- session metadata changes must stay with memory gate changes because the gate
  reads collaboration state from persisted session entries
- `src/memory-host-sdk/events.ts` belongs here because publish emits explicit
  collaboration memory events

### PR 5 - Collaboration schedules and approval policies

Intent:

- compile collaboration schedules into cron visible virtual jobs
- enforce collaboration approval policy on Slack approval delivery

Files:

- `src/collaboration/approval-policy.ts`
- `src/collaboration/approval-policy.test.ts`
- `src/cron/collaboration-source.ts`
- `src/cron/isolated-agent/run.ts`
- `src/cron/isolated-agent/run.collaboration.test.ts`
- `src/cron/service/store.ts`
- `src/cron/service/ops.ts`
- `src/cron/service/state.ts`
- `src/cron/store.ts`
- `src/cron/types.ts`
- `src/cron/service.collaboration-schedules.test.ts`
- `src/gateway/server-cron.ts`
- `extensions/slack/src/approval-native.ts`
- `extensions/slack/src/approval-native.test.ts`
- `extensions/slack/src/exec-approvals.ts`
- `extensions/slack/src/exec-approvals.test.ts`
- `src/plugin-sdk/approval-delivery-helpers.ts`

Do not mix with:

- route takeover changes
- memory publish path changes

Verification:

- `pnpm test src/collaboration/approval-policy.test.ts src/cron/service.collaboration-schedules.test.ts src/cron/isolated-agent/run.collaboration.test.ts extensions/slack/src/approval-native.test.ts extensions/slack/src/exec-approvals.test.ts src/plugin-sdk/approval-delivery-helpers.test.ts`
- `openclaw cron list`
- `openclaw cron run collab:<jobId>`

Commit boundary notes:

- cron service changes and Slack approval changes are both required in this PR
  because the policy surface is not complete until the schedule and approval
  enforcement paths both consume collaboration metadata

### Cherry Pick Strategy

If cutting PRs from the current worktree instead of rebuilding each slice from
scratch:

1. land `PR 0` first because it is independent and unblocks the old build error
2. extract `PR 1` next because all later slices depend on the config surface
3. extract `PR 2` before Slack runtime changes so reviewers can inspect
   explain and audit contracts in isolation
4. extract `PR 3` before memory and schedules because later slices depend on
   Slack managed surface metadata and handoff state
5. extract `PR 4` before `PR 5` because schedules and approvals rely on the
   collaboration session and memory metadata already existing

When staging from the current worktree:

- stage by file, not by `git add -A`
- keep generated baseline hash files only with the PR that introduces the
  corresponding public surface change
- if a file contains both route and memory edits, split hunks instead of
  widening the PR

### Files That Must Not Drift Across PRs

- `docs/.generated/config-baseline.sha256` must stay with the config schema PR
- `docs/.generated/plugin-sdk-api-baseline.sha256` must stay with the PR that
  changes `src/plugin-sdk/*`
- `scripts/lib/plugin-sdk-entrypoints.json` and `package.json` must stay with
  the PR that adds or changes plugin SDK public subpaths
- `src/channels/session.ts`, `src/channels/session.types.ts`,
  `src/config/sessions/store.ts`, and `src/config/sessions/types.ts` should
  stay together because partial staging here will break collaboration metadata
  propagation

## Acceptance Criteria

V1 should not be considered complete until all of the following are true on
managed Slack surfaces:

- each Slack user resolves to a stable collaboration identity
- each Slack surface resolves to exactly one collaboration space
- each inbound message resolves to exactly one owner agent
- private memory is not readable outside its allowed boundary
- role shared and space shared memory are readable only where policy permits
- ordinary bot messages do not trigger collaboration loops
- explicit handoffs can occur in the same Slack thread with bounded depth
- collaboration schedules can target an identity, role, or space
- approval decisions depend on collaboration policy, not channel membership
- explain output can justify the route, permissions, and readable scopes

## Open Questions

The following decisions should be frozen before implementation reaches schedule
and approval enforcement:

- whether `ceo` may publish directly into `space_shared` in all project spaces
  or only selected ones
- whether role targeted schedules may deliver into project channels by default
- whether any collaboration managed space should allow child handoffs to open a
  new thread instead of always replying in the owner thread

## Related Docs

- [Configuration Reference](/gateway/configuration-reference)
- [Slack](/channels/slack)
- [Multi Agent](/concepts/multi-agent)
- [Cron Jobs](/automation/cron-jobs)
