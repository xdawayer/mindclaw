# Slack Team Collaboration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a collaboration layer above the existing Slack channel so OpenClaw can support private DM spaces, project and role spaces, multi-agent routing (`ops`, `product`, `ceo`), sticky thread ownership, and project-aware cron delivery defaults without replacing the existing Slack transport.

**Architecture:** Reuse the existing Slack channel plugin, multi-agent bindings, and cron delivery stack. Add a new top-level `collaboration` config surface plus small runtime helpers for space lookup, identity resolution, routing overrides, thread ownership, consultation/handoff semantics, and project-aware cron target resolution. Phase the work so Slack message transport stays stable while team collaboration logic is layered above it.

**Tech Stack:** TypeScript, Zod config schemas, existing Slack Bolt channel plugin, existing multi-agent routing modules, existing cron delivery plan modules, Vitest.

---

### Task 1: Create the collaboration config surface

**Files:**

- Create: `src/config/types.collaboration.ts`
- Create: `src/config/zod-schema.collaboration.ts`
- Modify: `src/config/types.openclaw.ts`
- Modify: `src/config/zod-schema.ts`
- Modify: `src/config/schema.labels.ts`
- Modify: `src/config/schema.help.ts`
- Test: `src/config/zod-schema.collaboration.test.ts`

**Step 1: Write the failing config-schema test**

Add tests that parse:

- `collaboration.identities.users`
- `collaboration.spaces.projects`
- `collaboration.spaces.roles`
- `collaboration.routing`
- `collaboration.sync.dmToShared`

Also add one negative test for invalid `defaultAgent` and malformed Slack user/channel IDs.

**Step 2: Run test to verify it fails**

Run: `pnpm test src/config/zod-schema.collaboration.test.ts`
Expected: FAIL because the schema and types do not exist yet.

**Step 3: Add the minimal config types and Zod schema**

Implement:

- collaboration identity records keyed by Slack user ID
- project space records with `channelId`, `defaultAgent`, `defaultDmRecipient`, and `roleDmRecipients`
- role space records with `channelId` and `agentId`
- routing policy flags
- DM-to-shared sync policy

Wire the new schema into the root `OpenClawSchema` and `OpenClawConfig`.

**Step 4: Run test to verify it passes**

Run: `pnpm test src/config/zod-schema.collaboration.test.ts`
Expected: PASS

**Step 5: Commit**

```bash
scripts/committer "config: add collaboration schema" \
  src/config/types.collaboration.ts \
  src/config/zod-schema.collaboration.ts \
  src/config/types.openclaw.ts \
  src/config/zod-schema.ts \
  src/config/schema.labels.ts \
  src/config/schema.help.ts \
  src/config/zod-schema.collaboration.test.ts
```

### Task 2: Add collaboration runtime helpers for spaces and identities

**Files:**

- Create: `src/collaboration/types.ts`
- Create: `src/collaboration/identities.ts`
- Create: `src/collaboration/spaces.ts`
- Create: `src/collaboration/slack-targets.ts`
- Test: `src/collaboration/identities.test.ts`
- Test: `src/collaboration/spaces.test.ts`
- Test: `src/collaboration/slack-targets.test.ts`

**Step 1: Write failing unit tests**

Cover:

- resolving a Slack user to one or more OpenClaw roles
- resolving a Slack channel to project-space or role-space metadata
- resolving project DM targets with per-role override fallback
- preserving strict DM/project/role separation in returned space descriptors

**Step 2: Run tests to verify they fail**

Run: `pnpm test src/collaboration/identities.test.ts src/collaboration/spaces.test.ts src/collaboration/slack-targets.test.ts`
Expected: FAIL because the helper modules do not exist.

**Step 3: Implement minimal helpers**

Implement pure helpers only. Do not touch Slack runtime yet.

Key functions:

- resolve user roles from `collaboration.identities.users`
- resolve project space by Slack channel ID
- resolve role space by Slack channel ID
- resolve project default DM recipient and per-role override recipient

**Step 4: Run tests to verify they pass**

Run: `pnpm test src/collaboration/identities.test.ts src/collaboration/spaces.test.ts src/collaboration/slack-targets.test.ts`
Expected: PASS

**Step 5: Commit**

```bash
scripts/committer "collaboration: add space and identity helpers" \
  src/collaboration/types.ts \
  src/collaboration/identities.ts \
  src/collaboration/spaces.ts \
  src/collaboration/slack-targets.ts \
  src/collaboration/identities.test.ts \
  src/collaboration/spaces.test.ts \
  src/collaboration/slack-targets.test.ts
```

### Task 3: Route Slack conversations into project and role spaces

**Files:**

- Modify: `extensions/slack/src/channel.ts`
- Modify: `src/routing/resolve-route.ts`
- Create: `src/routing/slack-collaboration-routing.ts`
- Test: `src/routing/slack-collaboration-routing.test.ts`
- Test: `extensions/slack/src/channel.collaboration-routing.test.ts`

**Step 1: Write the failing routing tests**

Cover:

- project channel falls back to its configured default agent
- role channel routes directly to its role agent
- explicit `@ops`, `@product`, `@ceo` override the project default
- non-collaboration channels keep existing Slack routing behavior

**Step 2: Run tests to verify they fail**

Run: `pnpm test src/routing/slack-collaboration-routing.test.ts extensions/slack/src/channel.collaboration-routing.test.ts`
Expected: FAIL because collaboration-aware routing is not wired in yet.

**Step 3: Implement routing helper and Slack integration**

Implement a narrow collaboration routing helper that:

- inspects Slack channel and message metadata
- resolves collaboration space
- returns explicit override agent when a role mention is present
- otherwise returns the configured project or role default

Keep the existing binding and route resolution flow intact. This helper should augment routing, not replace it.

**Step 4: Run tests to verify they pass**

Run: `pnpm test src/routing/slack-collaboration-routing.test.ts extensions/slack/src/channel.collaboration-routing.test.ts`
Expected: PASS

**Step 5: Commit**

```bash
scripts/committer "routing: add Slack collaboration defaults" \
  extensions/slack/src/channel.ts \
  src/routing/resolve-route.ts \
  src/routing/slack-collaboration-routing.ts \
  src/routing/slack-collaboration-routing.test.ts \
  extensions/slack/src/channel.collaboration-routing.test.ts
```

### Task 4: Add classifier fallback for unspecified project-channel messages

**Files:**

- Modify: `src/routing/intent-routing.ts`
- Modify: `src/routing/route-with-intent-fallback.ts`
- Create: `src/routing/slack-collaboration-intent.ts`
- Test: `src/routing/slack-collaboration-intent.test.ts`

**Step 1: Write the failing intent-routing tests**

Cover:

- explicit role mention bypasses classifier
- unspecified project-channel message uses project default immediately
- high-confidence classifier result can transfer away from the default
- low-confidence classifier result keeps the default

**Step 2: Run tests to verify they fail**

Run: `pnpm test src/routing/slack-collaboration-intent.test.ts`
Expected: FAIL because collaboration intent policy does not exist.

**Step 3: Implement collaboration-aware intent fallback**

Add a thin policy wrapper around the existing intent-routing modules rather than forking them.

The wrapper must:

- disable classifier when explicit role mention exists
- seed the classifier with only the agents allowed in the relevant project space
- preserve the existing confidence gate behavior

**Step 4: Run tests to verify they pass**

Run: `pnpm test src/routing/slack-collaboration-intent.test.ts`
Expected: PASS

**Step 5: Commit**

```bash
scripts/committer "routing: add project-channel intent fallback" \
  src/routing/intent-routing.ts \
  src/routing/route-with-intent-fallback.ts \
  src/routing/slack-collaboration-intent.ts \
  src/routing/slack-collaboration-intent.test.ts
```

### Task 5: Persist sticky thread ownership for Slack project threads

**Files:**

- Create: `src/collaboration/thread-ownership.ts`
- Create: `src/collaboration/thread-ownership.store.ts`
- Modify: `extensions/slack/src/monitor/message-handler.ts`
- Modify: `extensions/slack/src/channel.ts`
- Test: `src/collaboration/thread-ownership.test.ts`
- Test: `extensions/slack/src/monitor.thread-ownership.test.ts`

**Step 1: Write the failing thread-ownership tests**

Cover:

- first routed message claims a thread owner
- subsequent messages in the same thread stay on the owner agent
- explicit role mention switches owner
- internal consultation does not switch owner
- root-channel messages without a thread do not mutate thread ownership

**Step 2: Run tests to verify they fail**

Run: `pnpm test src/collaboration/thread-ownership.test.ts extensions/slack/src/monitor.thread-ownership.test.ts`
Expected: FAIL because thread ownership state is missing.

**Step 3: Implement sticky ownership state**

Use a minimal store keyed by:

- Slack account
- channel ID
- thread TS

Store:

- owner agent ID
- last activity timestamp
- last explicit switch timestamp

Wire lookup into inbound Slack message handling before route finalization.

**Step 4: Run tests to verify they pass**

Run: `pnpm test src/collaboration/thread-ownership.test.ts extensions/slack/src/monitor.thread-ownership.test.ts`
Expected: PASS

**Step 5: Commit**

```bash
scripts/committer "slack: add sticky collaboration thread ownership" \
  src/collaboration/thread-ownership.ts \
  src/collaboration/thread-ownership.store.ts \
  extensions/slack/src/monitor/message-handler.ts \
  extensions/slack/src/channel.ts \
  src/collaboration/thread-ownership.test.ts \
  extensions/slack/src/monitor.thread-ownership.test.ts
```

### Task 6: Introduce explicit collaboration memory scopes

**Files:**

- Create: `src/collaboration/memory-scopes.ts`
- Modify: `extensions/memory-core/src/memory/manager-provider-state.ts`
- Modify: `extensions/memory-core/src/runtime-provider.ts`
- Test: `src/collaboration/memory-scopes.test.ts`
- Test: `extensions/memory-core/src/memory/collaboration-scopes.test.ts`

**Step 1: Write the failing memory-scope tests**

Cover:

- DM messages map to `private:<slackUserId>`
- project channels map to `project:<projectId>`
- role channels map to `role:<roleId>`
- DM content never auto-writes to project or role memory

**Step 2: Run tests to verify they fail**

Run: `pnpm test src/collaboration/memory-scopes.test.ts extensions/memory-core/src/memory/collaboration-scopes.test.ts`
Expected: FAIL because collaboration scope resolution is missing.

**Step 3: Implement collaboration scope resolution**

Keep this helper pure and composable. Resolve a memory scope from:

- channel type
- collaboration space metadata
- Slack user ID for DM

Then thread it into the memory-core runtime where the session context is built.

**Step 4: Run tests to verify they pass**

Run: `pnpm test src/collaboration/memory-scopes.test.ts extensions/memory-core/src/memory/collaboration-scopes.test.ts`
Expected: PASS

**Step 5: Commit**

```bash
scripts/committer "memory: add collaboration scope isolation" \
  src/collaboration/memory-scopes.ts \
  extensions/memory-core/src/memory/manager-provider-state.ts \
  extensions/memory-core/src/runtime-provider.ts \
  src/collaboration/memory-scopes.test.ts \
  extensions/memory-core/src/memory/collaboration-scopes.test.ts
```

### Task 7: Add project-aware cron target resolution

**Files:**

- Create: `src/cron/collaboration-delivery.ts`
- Modify: `src/cron/delivery-plan.ts`
- Modify: `src/cron/types.ts`
- Test: `src/cron/collaboration-delivery.test.ts`
- Test: `src/cron/delivery.test.ts`

**Step 1: Write the failing cron-delivery tests**

Cover:

- success-like events default to DM
- failure-like events default to project channel
- role-specific DM overrides beat the project default DM recipient
- explicit job `delivery` still wins over collaboration defaults
- explicit job `failureDestination` still wins over collaboration defaults

**Step 2: Run tests to verify they fail**

Run: `pnpm test src/cron/collaboration-delivery.test.ts src/cron/delivery.test.ts`
Expected: FAIL because collaboration delivery policy is not implemented.

**Step 3: Implement a collaboration delivery resolver**

Do not rewrite cron delivery semantics. Instead:

- derive collaboration defaults from project metadata
- map them into the existing `CronDeliveryPlan`
- preserve current `delivery` and `failureDestination` precedence

**Step 4: Run tests to verify they pass**

Run: `pnpm test src/cron/collaboration-delivery.test.ts src/cron/delivery.test.ts`
Expected: PASS

**Step 5: Commit**

```bash
scripts/committer "cron: add project-aware collaboration delivery defaults" \
  src/cron/collaboration-delivery.ts \
  src/cron/delivery-plan.ts \
  src/cron/types.ts \
  src/cron/collaboration-delivery.test.ts \
  src/cron/delivery.test.ts
```

### Task 8: Add collaboration-aware Slack message presentation

**Files:**

- Create: `extensions/slack/src/collaboration-presentation.ts`
- Modify: `extensions/slack/src/send.ts`
- Modify: `extensions/slack/src/blocks-render.ts`
- Test: `extensions/slack/src/collaboration-presentation.test.ts`
- Test: `extensions/slack/src/send.blocks.test.ts`

**Step 1: Write the failing presentation tests**

Cover:

- default Slack replies still look like plain `OpenClaw`
- explicit role route can add a small owner label
- consultation summary can attribute consulted agents when needed
- root behavior remains unchanged for non-collaboration Slack accounts

**Step 2: Run tests to verify they fail**

Run: `pnpm test extensions/slack/src/collaboration-presentation.test.ts extensions/slack/src/send.blocks.test.ts`
Expected: FAIL because collaboration presentation hooks do not exist.

**Step 3: Implement minimal presentation helper**

The helper should:

- keep one Slack outward identity
- optionally inject owner attribution in text or blocks
- avoid role labels on every ordinary message

**Step 4: Run tests to verify they pass**

Run: `pnpm test extensions/slack/src/collaboration-presentation.test.ts extensions/slack/src/send.blocks.test.ts`
Expected: PASS

**Step 5: Commit**

```bash
scripts/committer "slack: add collaboration owner presentation" \
  extensions/slack/src/collaboration-presentation.ts \
  extensions/slack/src/send.ts \
  extensions/slack/src/blocks-render.ts \
  extensions/slack/src/collaboration-presentation.test.ts \
  extensions/slack/src/send.blocks.test.ts
```

### Task 9: Add DM-to-shared sync request and approval primitives

**Files:**

- Create: `src/collaboration/sync-requests.ts`
- Create: `src/collaboration/sync-approvals.ts`
- Modify: `extensions/slack/src/monitor/slash.ts`
- Modify: `extensions/slack/src/blocks-render.ts`
- Test: `src/collaboration/sync-requests.test.ts`
- Test: `src/collaboration/sync-approvals.test.ts`
- Test: `extensions/slack/src/monitor.slash.sync.test.ts`

**Step 1: Write the failing sync tests**

Cover:

- DM user can request sync into a target project space
- sync request is not auto-applied
- approval target resolves to the configured project default agent or approver
- approved sync writes only the selected content into shared scope

**Step 2: Run tests to verify they fail**

Run: `pnpm test src/collaboration/sync-requests.test.ts src/collaboration/sync-approvals.test.ts extensions/slack/src/monitor.slash.sync.test.ts`
Expected: FAIL because sync request and approval behavior is missing.

**Step 3: Implement the minimal request/approval path**

For the first version:

- support a request object
- support a single approver resolution rule
- do not build the full Slack control panel yet
- expose one Slack-native slash/interactive path to approve or reject

**Step 4: Run tests to verify they pass**

Run: `pnpm test src/collaboration/sync-requests.test.ts src/collaboration/sync-approvals.test.ts extensions/slack/src/monitor.slash.sync.test.ts`
Expected: PASS

**Step 5: Commit**

```bash
scripts/committer "collaboration: add DM-to-shared sync approvals" \
  src/collaboration/sync-requests.ts \
  src/collaboration/sync-approvals.ts \
  extensions/slack/src/monitor/slash.ts \
  extensions/slack/src/blocks-render.ts \
  src/collaboration/sync-requests.test.ts \
  src/collaboration/sync-approvals.test.ts \
  extensions/slack/src/monitor.slash.sync.test.ts
```

### Task 10: Add agent consultation and explicit handoff mechanics

**Files:**

- Create: `src/collaboration/consultation.ts`
- Create: `src/collaboration/handoff.ts`
- Modify: `src/routing/routing-hooks.ts`
- Modify: `src/channels/plugins/conversation-bindings.ts`
- Test: `src/collaboration/consultation.test.ts`
- Test: `src/collaboration/handoff.test.ts`

**Step 1: Write the failing collaboration-flow tests**

Cover:

- owner agent can consult another role without transferring owner
- explicit handoff changes thread owner
- consultation passes only minimal allowed context
- private DM scope is not forwarded into shared consultation automatically

**Step 2: Run tests to verify they fail**

Run: `pnpm test src/collaboration/consultation.test.ts src/collaboration/handoff.test.ts`
Expected: FAIL because consultation and handoff semantics do not exist.

**Step 3: Implement consultation and handoff primitives**

Keep this layer host-agnostic:

- consultation returns results to the owner
- handoff updates sticky ownership
- routing hooks may consume the new handoff state

**Step 4: Run tests to verify they pass**

Run: `pnpm test src/collaboration/consultation.test.ts src/collaboration/handoff.test.ts`
Expected: PASS

**Step 5: Commit**

```bash
scripts/committer "collaboration: add consultation and handoff primitives" \
  src/collaboration/consultation.ts \
  src/collaboration/handoff.ts \
  src/routing/routing-hooks.ts \
  src/channels/plugins/conversation-bindings.ts \
  src/collaboration/consultation.test.ts \
  src/collaboration/handoff.test.ts
```

### Task 11: Document the new collaboration model

**Files:**

- Modify: `docs/channels/slack.md`
- Modify: `docs/automation/cron-jobs.md`
- Modify: `docs/concepts/multi-agent.md`
- Modify: `docs/gateway/configuration-reference.md`
- Modify: `docs/channels/channel-routing.md`
- Test: generated config docs hash output

**Step 1: Write the docs changes**

Document:

- collaboration config shape
- project spaces vs role spaces
- explicit mention routing
- sticky thread ownership
- cron project-aware defaults
- DM-to-shared sync approval behavior

**Step 2: Run config docs generation**

Run: `pnpm config:docs:gen`
Expected: updated generated schema artifacts and hash files if the public config surface changed.

**Step 3: Run targeted docs and schema verification**

Run: `pnpm config:docs:check`
Expected: PASS

**Step 4: Commit**

```bash
scripts/committer "docs: add Slack collaboration and cron routing docs" \
  docs/channels/slack.md \
  docs/automation/cron-jobs.md \
  docs/concepts/multi-agent.md \
  docs/gateway/configuration-reference.md \
  docs/channels/channel-routing.md
```

### Task 12: Run final focused verification for the collaboration feature

**Files:**

- Modify: none
- Verify: all collaboration-related files above

**Step 1: Run focused collaboration verification**

Run:

```bash
pnpm test \
  src/config/zod-schema.collaboration.test.ts \
  src/collaboration/identities.test.ts \
  src/collaboration/spaces.test.ts \
  src/collaboration/slack-targets.test.ts \
  src/routing/slack-collaboration-routing.test.ts \
  src/routing/slack-collaboration-intent.test.ts \
  src/collaboration/thread-ownership.test.ts \
  src/collaboration/memory-scopes.test.ts \
  src/cron/collaboration-delivery.test.ts \
  src/collaboration/sync-requests.test.ts \
  src/collaboration/sync-approvals.test.ts \
  src/collaboration/consultation.test.ts \
  src/collaboration/handoff.test.ts \
  extensions/slack/src/channel.collaboration-routing.test.ts \
  extensions/slack/src/monitor.thread-ownership.test.ts \
  extensions/slack/src/collaboration-presentation.test.ts \
  extensions/slack/src/monitor.slash.sync.test.ts
```

Expected: PASS

**Step 2: Run the repo quality gates that are required by this surface**

Run:

```bash
pnpm check
pnpm test
```

Expected: PASS

**Step 3: Commit**

```bash
git status --short
```

Confirm only the intended collaboration files are staged for the final landing commit(s).

## Notes For Execution

- Keep Phase 1 shippable on its own. Do not block ordinary Slack message transport on later consultation or control-panel work.
- Prefer pure helpers and small routing adapters over deep changes inside the Slack transport.
- Treat DM/private memory leakage as a security bug, not a UX bug.
- Preserve existing Slack behavior for users who do not configure the new collaboration surface.
- When modifying public config, keep `schema.help`, labels, generated docs, and drift checks aligned.

## Suggested Execution Order

Implement in this order:

1. config surface
2. collaboration runtime helpers
3. base Slack routing
4. classifier fallback
5. sticky thread ownership
6. memory scopes
7. cron delivery defaults
8. Slack presentation tweaks
9. DM sync approvals
10. consultation and handoff
11. docs
12. final verification

Plan complete and saved to `docs/plans/2026-04-22-slack-team-collaboration-implementation.md`. Two execution options:

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

Which approach?
