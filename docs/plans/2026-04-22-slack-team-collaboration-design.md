# Slack Team Collaboration Design

## Goal

Turn Slack into a first-class OpenClaw collaboration surface for:

- ordinary DM and channel conversations
- project-scoped shared work
- role-specific agent collaboration across `ops`, `product`, and `ceo`
- cron delivery that respects project and role ownership
- strict isolation for private, project, and role memory domains

This design assumes one Slack workspace in the first shipping phase, with room to expand to multiple workspaces later without changing the core model.

## Non-goals

- multiple visible Slack bot identities in Phase 1
- fully automatic cross-project reasoning or memory sharing
- multi-workspace support in the first rollout
- a full Slack control panel before the core routing and isolation model is stable

## Existing Foundation In The Repo

Slack transport is already present and production-ready enough to avoid rewriting the connector layer:

- Slack channel docs and setup: `docs/channels/slack.md`
- Slack monitor entrypoint: `extensions/slack/src/index.ts`
- inbound message handling: `extensions/slack/src/monitor/message-handler.ts`
- outbound send path: `extensions/slack/src/send.ts`
- Slack interactive blocks rendering: `extensions/slack/src/blocks-render.ts`
- Slack slash/native command handling: `extensions/slack/src/monitor/slash.ts`

Cron already supports direct announce delivery to Slack targets:

- scheduler behavior and delivery model: `docs/automation/cron-jobs.md`
- cron delivery types: `src/cron/types.ts`
- cron delivery planning: `src/cron/delivery-plan.ts`

Multi-agent routing already exists and should be reused instead of inventing a second routing stack:

- multi-agent concept doc: `docs/concepts/multi-agent.md`
- bindings and agent isolation: `src/config/zod-schema.agents.ts`, `src/routing/resolve-route.ts`
- intent fallback hooks: `src/routing/intent-routing.ts`, `src/routing/route-with-intent-fallback.ts`
- routing hook registry: `src/routing/routing-hooks.ts`

## Approved Product Decisions

The design below reflects the decisions already made:

- Slack is first an ordinary conversation entrypoint.
- Cron messages matter and must route cleanly.
- Phase 1 starts with a single Slack workspace.
- Project channels are allowed to accept ordinary conversation directly.
- Replies follow chat shape:
  - channel messages reply in channel
  - thread replies continue in thread
- Workspace model is two-level:
  - private personal DM space
  - shared project and role spaces
- Shared spaces are dual-axis:
  - project channels are the main work surface
  - role channels are cross-project viewpoints
- Memory policy:
  - DM memory stays private by default
  - project channels write project-shared memory
  - role channels write role-shared memory
  - DM to shared-domain sync requires explicit action
- Access model:
  - Slack membership controls visibility and who can speak
  - OpenClaw role policy controls privileged actions
- Role source:
  - OpenClaw stores the final role mapping
  - Slack groups may import or sync into it later
- `ops`, `product`, and `ceo` are independent agents, not permission labels.
- Project channels support multiple coexisting agents.
- Routing priority:
  - explicit mention wins
  - otherwise default agent plus classifier fallback
- Threads are sticky:
  - once a thread lands on an agent, it stays there until explicit handoff
- Outward identity:
  - default visible identity is still `OpenClaw`
  - key replies may indicate the active agent
- Project channels define their own default agent.
- Cron DM targets use mixed defaults:
  - project default DM recipient
  - optional per-role DM recipient overrides
- DM to shared-space sync uses approval:
  - the sender can request it
  - entry into shared memory requires approval
- Agent-to-agent collaboration should work:
  - `ceo` can consult `ops` or `product`
  - default consultation does not transfer thread ownership
  - explicit handoff does transfer ownership

## Core Model

### 1. Spaces

OpenClaw should introduce an explicit collaboration-space layer above raw Slack channels.

There are four space types:

- `private`
  - one per Slack user DM with OpenClaw
  - stores private message history and private memory
- `project`
  - one per project channel
  - primary shared workspace
- `role`
  - one per role channel such as `ops`, `product`, or `ceo`
  - cross-project view, not the default execution surface
- `thread`
  - a routing overlay inside a project or role space
  - used to persist the current thread owner and collaboration state

Slack is only the host channel system. The durable logic lives in OpenClaw space metadata.

### 2. Agents

Agents remain first-class isolated OpenClaw agents:

- `ops`
- `product`
- `ceo`

Each has its own:

- workspace
- prompt and identity rules
- tool policy
- memory scope defaults
- session store

This is already aligned with the current multi-agent architecture in the repo.

### 3. Identity and roles

Slack user membership answers:

- who can see a channel
- who can speak in a channel

OpenClaw collaboration identity answers:

- who is `ops`, `product`, or `ceo`
- who can approve DM-to-shared sync
- who can change cron routing
- who can perform high-trust actions later

The final source of truth lives in OpenClaw config. Slack groups may be imported into that model, but they are not the final authority.

## Routing Design

### 1. Base deterministic routing

The existing routing stack remains the first layer:

- configured bindings route a Slack channel to a default agent
- project channels therefore bind to one explicit default agent
- role channels bind directly to their role agent
- DMs bind to the user's private-space policy

This keeps Phase 1 compatible with today's routing behavior.

### 2. Explicit mention routing

Explicit mention of a role agent inside a project thread overrides the channel default.

Examples:

- `@ops`
- `@product`
- `@ceo`

Behavior:

- if the message starts a new thread, ownership is assigned to the mentioned agent
- if the message arrives in an existing thread, ownership switches to the mentioned agent
- explicit mention always wins over intent classification

### 3. Intent fallback routing

When no explicit mention is present:

1. use the project channel's configured default agent immediately
2. optionally run classifier-based routing in the background
3. if confidence is high enough and differs from the default, transfer to the better agent
4. if confidence is low, stay on the default agent

This matches the existing `routeWithIntentFallback` pattern rather than inventing a new async routing mechanism.

### 4. Sticky thread ownership

Project threads must persist ownership.

Rules:

- each thread has exactly one current owner agent
- follow-up messages in the thread go to the owner by default
- consultation with another agent does not change ownership
- only explicit mention or explicit handoff changes ownership

This reduces agent flapping and preserves memory consistency.

## Agent-To-Agent Collaboration

### 1. Consultation

Consultation is a bounded internal delegation:

- current owner asks another agent a focused question
- target agent receives only the minimum required context
- result is returned to the owner agent
- owner agent synthesizes the final Slack reply

Example:

- user asks `@ceo should we increase budget?`
- thread owner becomes `ceo`
- `ceo` consults `ops` for execution risk
- `ceo` consults `product` for user impact
- `ceo` returns a single integrated answer

### 2. Handoff

Handoff is different from consultation:

- thread ownership changes
- future messages default to the new owner
- handoff must be explicit, not implicit

### 3. Visible behavior in Slack

Slack still shows one OpenClaw identity by default.

The active agent label appears only when useful:

- explicit mention routing
- explicit handoff
- approval decisions
- cron notifications where ownership matters
- internal-consultation summaries when attribution improves clarity

This preserves a clean Slack surface without hiding ownership when it matters.

## Isolation Model

### 1. Message isolation

- DM conversation history stays in the user's private space
- project-channel history stays in the project space
- role-channel history stays in the role space
- thread ownership metadata stays attached to the owning space and thread

### 2. Memory isolation

Recommended memory scopes:

- `private:<slackUserId>`
- `project:<projectId>`
- `role:<roleId>`

Default rules:

- DM writes only to `private:*`
- project channel writes only to `project:*`
- role channel writes only to `role:*`
- consultation across agents may read project or role shared memory when allowed
- consultation never implicitly imports private memory from another user

### 3. DM to shared sync

DM content can only enter shared memory by explicit request.

Flow:

1. user requests sync from private DM
2. OpenClaw creates a sync proposal
3. configured approver, project default agent, or approval rule confirms once
4. approved content is copied into the shared scope with provenance

Rejected or unapproved requests remain private.

## Cron And Notification Model

### 1. Project-level delivery policy

Cron should not encode Slack organization logic itself. Instead, project policy resolves to existing cron delivery fields.

Each project space defines:

- project channel target
- default DM recipient
- optional per-role DM recipient overrides
- default agent

### 2. Default notification policy

Defaults:

- `failure`, `alert`, `blocker`, `approval-needed`
  - route to project channel
- `routine`, `digest`, `reminder`, `success`
  - route to DM

DM resolution:

- prefer the target role's DM recipient override
- otherwise use the project's default DM recipient

### 3. Resolution priority

Cron destination priority should be:

1. explicit job `delivery`
2. explicit job `delivery.failureDestination`
3. project role DM override
4. project default DM recipient or project channel target
5. global cron failure destination or current fallback behavior

### 4. Thread behavior

Channel notifications default to the channel root, not a thread.

Only explicit `threadId` settings should place delivery into a thread.

This keeps alerts visible in the first production phase.

## Configuration Model

Add a new top-level `collaboration` config surface instead of overloading `channels.slack`.

High-level shape:

```json5
{
  collaboration: {
    identities: {
      users: {
        U_PM_1: { roles: ["product"] },
        U_OPS_1: { roles: ["ops"] },
        U_CEO_1: { roles: ["ceo"] },
      },
    },
    spaces: {
      projects: {
        "proj-a": {
          channelId: "C_PROJ_A",
          defaultAgent: "product",
          defaultDmRecipient: "U_PM_1",
          roleDmRecipients: {
            ops: "U_OPS_1",
            ceo: "U_CEO_1",
          },
        },
      },
      roles: {
        ops: { channelId: "C_ROLE_OPS", agentId: "ops" },
        product: { channelId: "C_ROLE_PRODUCT", agentId: "product" },
        ceo: { channelId: "C_ROLE_CEO", agentId: "ceo" },
      },
    },
    routing: {
      explicitMentionsOverride: true,
      autoClassifyWhenUnspecified: true,
      stickyThreadOwner: true,
      internalConsultationChangesOwner: false,
    },
    sync: {
      dmToShared: {
        mode: "request-approval",
        approver: "space-default-agent",
      },
    },
  },
}
```

This model intentionally composes with:

- `agents.list`
- `bindings`
- `channels.slack`
- `cron.delivery`

Instead of replacing them.

## Phase Plan

### Phase 1: Slack entrypoint and cron routing baseline

- single Slack workspace
- ordinary DM and project-channel conversation
- project space model
- project-level cron routing defaults
- no complex internal consultation yet

### Phase 2: multi-agent project routing

- explicit `@ops / @product / @ceo`
- default agent plus classifier fallback
- sticky thread ownership
- memory scopes for private/project/role domains

### Phase 3: internal consultation and control surface

- agent-to-agent consultation
- explicit handoff
- DM-to-shared approval workflow
- Slack interaction controls for owner, handoff, sync, and cron routing

## Risks

### Routing ambiguity

Automatic classification can fight user intent if explicit mentions do not have hard precedence. This is why explicit mention must always override classifier output.

### Hidden memory leakage

The biggest product risk is accidental movement of private DM context into project or role memory. The system must enforce explicit sync requests and approval before writing to shared scopes.

### Thread confusion

Without sticky thread ownership, multi-agent routing will feel random. Ownership must be visible in logs and selectively visible in Slack.

### Slack-only modeling mistakes

If collaboration semantics are embedded directly inside `channels.slack.*`, the design will become hard to extend to other channels or future workspace shapes. The collaboration model should remain host-agnostic.

## Why This Design

This design keeps the repo's existing strengths:

- reuse current Slack transport
- reuse current multi-agent isolation
- reuse current cron delivery model
- add team collaboration as a thin but explicit control layer

It avoids the two failure modes most likely to hurt the product:

- overloading Slack channel config with product semantics
- overexposing multiple visible bot identities before the collaboration model is stable

The result is a system where Slack is the visible front door, but OpenClaw remains the real owner of routing, isolation, memory, and team coordination logic.
