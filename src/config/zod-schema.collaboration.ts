import { z } from "zod";
import { isValidAgentId } from "../routing/session-key.js";

const SlackUserIdSchema = z
  .string()
  .trim()
  .regex(/^(U|W)[A-Z0-9]+$/i, "Expected Slack user id like U123ABC456");

const SlackChannelIdSchema = z
  .string()
  .trim()
  .regex(/^(C|G)[A-Z0-9]+$/i, "Expected Slack channel id like C123ABC456");

const CollaborationAgentIdSchema = z
  .string()
  .trim()
  .min(1)
  .refine((value) => isValidAgentId(value), "Invalid agent id");

const CollaborationRoleIdSchema = z.string().trim().min(1);
const CollaborationSpaceIdSchema = z.string().trim().min(1);

const CollaborationUserIdentitySchema = z
  .object({
    roles: z.array(CollaborationRoleIdSchema).optional(),
    slackGroups: z.array(z.string().trim().min(1)).optional(),
  })
  .strict();

const CollaborationIdentitiesSchema = z
  .object({
    users: z.record(SlackUserIdSchema, CollaborationUserIdentitySchema).optional(),
  })
  .strict();

const CollaborationProjectSpaceSchema = z
  .object({
    channelId: SlackChannelIdSchema,
    defaultAgent: CollaborationAgentIdSchema,
    defaultDmRecipient: SlackUserIdSchema,
    roleDmRecipients: z.record(CollaborationRoleIdSchema, SlackUserIdSchema).optional(),
  })
  .strict();

const CollaborationRoleSpaceSchema = z
  .object({
    channelId: SlackChannelIdSchema,
    agentId: CollaborationAgentIdSchema,
  })
  .strict();

const CollaborationSpacesSchema = z
  .object({
    projects: z.record(CollaborationSpaceIdSchema, CollaborationProjectSpaceSchema).optional(),
    roles: z.record(CollaborationRoleIdSchema, CollaborationRoleSpaceSchema).optional(),
  })
  .strict();

const CollaborationRoutingSchema = z
  .object({
    explicitMentionsOverride: z.boolean().optional(),
    autoClassifyWhenUnspecified: z.boolean().optional(),
    stickyThreadOwner: z.boolean().optional(),
    internalConsultationChangesOwner: z.boolean().optional(),
  })
  .strict();

const CollaborationSyncSchema = z
  .object({
    dmToShared: z
      .object({
        mode: z.literal("request-approval").optional(),
        approver: z.union([z.literal("space-default-agent"), SlackUserIdSchema]).optional(),
      })
      .strict()
      .optional(),
  })
  .strict();

export const CollaborationSchema = z
  .object({
    identities: CollaborationIdentitiesSchema.optional(),
    spaces: CollaborationSpacesSchema.optional(),
    routing: CollaborationRoutingSchema.optional(),
    sync: CollaborationSyncSchema.optional(),
  })
  .strict()
  .optional();
