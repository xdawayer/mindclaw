import { z } from "zod";

const CollaborationIdSchema = z
  .string()
  .regex(
    /^[a-z][a-z0-9_-]{1,63}$/,
    "Expected lowercase id with letters, numbers, underscores, or hyphens",
  );

const SlackSurfaceIdSchema = z.string().min(1);

const CollaborationMemoryScopeSchema = z.enum(["private", "role_shared", "space_shared"]);
const CollaborationPublishableMemoryScopeSchema = z.enum(["role_shared", "space_shared"]);

const CollaborationPermissionSchema = z.enum([
  "memory.read.private",
  "memory.read.role_shared",
  "memory.read.space_shared",
  "memory.write.private",
  "memory.publish.role_shared",
  "memory.publish.space_shared",
  "schedule.read",
  "schedule.create",
  "schedule.edit",
  "schedule.delete",
  "agent.handoff",
  "agent.mention",
  "exec.approve",
  "config.edit",
]);

const CollaborationIdentityBindingSchema = z
  .object({
    identityId: CollaborationIdSchema,
    displayName: z.string().optional(),
    roles: z.array(CollaborationIdSchema).min(1),
    defaultRole: CollaborationIdSchema.optional(),
    scheduleDelivery: z
      .object({
        preferDm: z.boolean().optional(),
        fallbackBotId: CollaborationIdSchema.optional(),
      })
      .strict()
      .optional(),
  })
  .strict()
  .superRefine((value, ctx) => {
    if (value.defaultRole && !value.roles.includes(value.defaultRole)) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["defaultRole"],
        message: "defaultRole must be included in roles",
      });
    }
  });

const CollaborationBotConfigSchema = z
  .object({
    slackAccountId: z.string().min(1),
    agentId: z.string().min(1),
    role: CollaborationIdSchema,
    displayName: z.string().optional(),
    identityStyle: z.enum(["role", "agent"]).optional(),
    allowedSpaces: z.array(CollaborationIdSchema).optional(),
    canInitiateHandoffs: z.boolean().optional(),
    canReceiveHandoffs: z.boolean().optional(),
  })
  .strict();

const CollaborationRoleConfigSchema = z
  .object({
    defaultAgentId: z.string().min(1),
    defaultBotId: CollaborationIdSchema,
    permissions: z.array(CollaborationPermissionSchema).min(1),
    memoryPolicy: z
      .object({
        defaultWriteScope: CollaborationMemoryScopeSchema.optional(),
        readableScopes: z.array(CollaborationMemoryScopeSchema).optional(),
        publishableScopes: z.array(CollaborationPublishableMemoryScopeSchema).optional(),
      })
      .strict()
      .optional(),
    schedulePolicy: z
      .object({
        canCreate: z.boolean().optional(),
        canEdit: z.boolean().optional(),
        canDelete: z.boolean().optional(),
        allowedAudienceKinds: z.array(z.enum(["identity", "role", "space"])).optional(),
        allowPrivateDigest: z.boolean().optional(),
      })
      .strict()
      .optional(),
  })
  .strict();

const CollaborationDeliveryTargetSchema = z.discriminatedUnion("kind", [
  z
    .object({
      kind: z.literal("slack_dm"),
      identityId: CollaborationIdSchema.optional(),
      roleId: CollaborationIdSchema.optional(),
    })
    .strict(),
  z
    .object({
      kind: z.literal("slack_channel"),
      channelId: SlackSurfaceIdSchema,
    })
    .strict(),
  z
    .object({
      kind: z.literal("space_default"),
      spaceId: CollaborationIdSchema,
    })
    .strict(),
]);

const CollaborationSpaceConfigSchema = z
  .object({
    kind: z.enum(["dm", "role", "project"]),
    displayName: z.string().optional(),
    ownerRole: CollaborationIdSchema.optional(),
    memberRoles: z.array(CollaborationIdSchema).optional(),
    slack: z
      .object({
        channels: z.array(SlackSurfaceIdSchema).optional(),
        users: z.array(SlackSurfaceIdSchema).optional(),
        requireMention: z.boolean().optional(),
        replyThreadMode: z.enum(["owner", "free", "strict_owner"]).optional(),
        allowBotMessages: z.enum(["none", "handoff_only"]).optional(),
      })
      .strict()
      .optional(),
    memory: z
      .object({
        sharedScopeId: z.string().optional(),
        readableByRoles: z.array(CollaborationIdSchema).optional(),
        writableByRoles: z.array(CollaborationIdSchema).optional(),
        publishRequires: z.array(CollaborationPermissionSchema).optional(),
      })
      .strict()
      .optional(),
    handoffs: z
      .object({
        allowedTargets: z.array(CollaborationIdSchema).optional(),
        requireExplicitMention: z.boolean().optional(),
        maxDepth: z.number().int().positive().optional(),
      })
      .strict()
      .optional(),
    schedules: z
      .object({
        allowed: z.boolean().optional(),
        defaultDestinations: z.array(CollaborationDeliveryTargetSchema).optional(),
        quietHours: z
          .object({
            tz: z.string().min(1),
            start: z.string().min(1),
            end: z.string().min(1),
          })
          .strict()
          .optional(),
      })
      .strict()
      .optional(),
  })
  .strict()
  .superRefine((value, ctx) => {
    if (value.kind === "dm") {
      if (!value.slack?.users || value.slack.users.length === 0) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["slack", "users"],
          message: "dm spaces require at least one Slack user in slack.users",
        });
      }
      return;
    }

    if (!value.ownerRole) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["ownerRole"],
        message: `${value.kind} spaces require ownerRole`,
      });
    }

    if (!value.memberRoles || value.memberRoles.length === 0) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["memberRoles"],
        message: `${value.kind} spaces require memberRoles`,
      });
      return;
    }

    if (value.ownerRole && !value.memberRoles.includes(value.ownerRole)) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["memberRoles"],
        message: `ownerRole "${value.ownerRole}" must be included in memberRoles`,
      });
    }
  });

const CollaborationMemoryConfigSchema = z
  .object({
    scopes: z
      .object({
        private: z
          .object({
            default: z.boolean().optional(),
          })
          .strict()
          .optional(),
        role_shared: z
          .object({
            partitionBy: z.literal("role"),
          })
          .strict()
          .optional(),
        space_shared: z
          .object({
            partitionBy: z.literal("space"),
          })
          .strict()
          .optional(),
      })
      .strict()
      .optional(),
    rules: z
      .object({
        requireProvenance: z.boolean().optional(),
        requireExplicitPublish: z.boolean().optional(),
        denyGlobalSearchByDefault: z.boolean().optional(),
      })
      .strict()
      .optional(),
  })
  .strict();

const CollaborationRoutingConfigSchema = z
  .object({
    ownerSelection: z
      .object({
        dm: z.literal("identity_default_role").optional(),
        role: z.literal("space_owner_role").optional(),
        project: z.literal("space_owner_role").optional(),
      })
      .strict()
      .optional(),
    mentionRouting: z
      .object({
        explicitAgentMention: z.boolean().optional(),
        fallbackToOwner: z.boolean().optional(),
      })
      .strict()
      .optional(),
    handoff: z
      .object({
        mode: z.literal("structured").optional(),
        dedupeWindow: z.string().min(1).optional(),
        maxDepth: z.number().int().positive().optional(),
        allowBotAuthoredReentry: z.boolean().optional(),
      })
      .strict()
      .optional(),
  })
  .strict();

const CollaborationScheduleAudienceSchema = z.discriminatedUnion("kind", [
  z
    .object({
      kind: z.literal("identity"),
      id: CollaborationIdSchema,
    })
    .strict(),
  z
    .object({
      kind: z.literal("role"),
      id: CollaborationIdSchema,
    })
    .strict(),
  z
    .object({
      kind: z.literal("space"),
      id: CollaborationIdSchema,
    })
    .strict(),
]);

const CollaborationScheduleJobSchema = z
  .object({
    id: CollaborationIdSchema,
    enabled: z.boolean().optional(),
    audience: CollaborationScheduleAudienceSchema,
    sourceSpaces: z.array(CollaborationIdSchema).min(1),
    at: z.string().min(1).optional(),
    every: z.string().min(1).optional(),
    cron: z.string().min(1).optional(),
    tz: z.string().min(1).optional(),
    delivery: z.array(CollaborationDeliveryTargetSchema).min(1),
    memoryReadScopes: z.array(CollaborationMemoryScopeSchema).optional(),
    template: z.string().optional(),
    systemPrompt: z.string().optional(),
    ownerRole: CollaborationIdSchema.optional(),
  })
  .strict()
  .superRefine((value, ctx) => {
    const selectors = [value.at, value.every, value.cron].filter((entry) => !!entry);
    if (selectors.length !== 1) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: [],
        message: 'Specify exactly one of "at", "every", or "cron"',
      });
    }
  });

const CollaborationSchedulesConfigSchema = z
  .object({
    jobs: z.array(CollaborationScheduleJobSchema),
  })
  .strict();

const CollaborationApprovalConfigSchema = z
  .object({
    policies: z.record(
      z.string().min(1),
      z
        .object({
          when: z.array(z.string().min(1)).min(1),
          approverRoles: z.array(CollaborationIdSchema).min(1),
          delivery: z.array(z.enum(["dm", "origin_thread"])).min(1),
          visibility: z.enum(["summary_only", "full_context"]).optional(),
          agentFilter: z.array(z.string().min(1)).optional(),
          spaceFilter: z.array(CollaborationIdSchema).optional(),
        })
        .strict(),
    ),
  })
  .strict();

const CollaborationAuditConfigSchema = z
  .object({
    enabled: z.boolean().optional(),
    retainDays: z.number().int().positive().optional(),
    redactBodies: z.boolean().optional(),
    explainMode: z.boolean().optional(),
  })
  .strict();

export const CollaborationConfigSchema = z
  .object({
    version: z.literal(1),
    mode: z.enum(["disabled", "shadow", "enforced"]).optional(),
    identities: z
      .object({
        users: z.record(z.string().min(1), CollaborationIdentityBindingSchema),
      })
      .strict(),
    bots: z.record(CollaborationIdSchema, CollaborationBotConfigSchema),
    roles: z.record(CollaborationIdSchema, CollaborationRoleConfigSchema),
    spaces: z.record(CollaborationIdSchema, CollaborationSpaceConfigSchema),
    memory: CollaborationMemoryConfigSchema.optional(),
    routing: CollaborationRoutingConfigSchema.optional(),
    schedules: CollaborationSchedulesConfigSchema.optional(),
    approvals: CollaborationApprovalConfigSchema.optional(),
    audit: CollaborationAuditConfigSchema.optional(),
  })
  .strict();
