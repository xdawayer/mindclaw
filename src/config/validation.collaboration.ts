import type { ConfigValidationIssue, OpenClawConfig } from "./types.js";

function pushIssue(issues: ConfigValidationIssue[], path: string, message: string): void {
  issues.push({ path, message });
}

function collectAgentIds(config: OpenClawConfig): Set<string> {
  return new Set(
    (config.agents?.list ?? [])
      .map((agent) => agent.id.trim())
      .filter((agentId) => agentId.length > 0),
  );
}

function collectSlackAccountIds(config: OpenClawConfig): Set<string> {
  return new Set(
    Object.keys(config.channels?.slack?.accounts ?? {})
      .map((accountId) => accountId.trim())
      .filter((accountId) => accountId.length > 0),
  );
}

function collectIdentityIds(config: NonNullable<OpenClawConfig["collaboration"]>): Set<string> {
  return new Set(
    Object.values(config.identities.users)
      .map((identity) => identity.identityId.trim())
      .filter((identityId) => identityId.length > 0),
  );
}

export function validateCollaborationConfig(config: OpenClawConfig): ConfigValidationIssue[] {
  const collaboration = config.collaboration;
  if (!collaboration) {
    return [];
  }

  const issues: ConfigValidationIssue[] = [];
  const agentIds = collectAgentIds(config);
  const slackAccountIds = collectSlackAccountIds(config);
  const identityIds = collectIdentityIds(collaboration);
  const botIds = new Set(Object.keys(collaboration.bots));
  const roleIds = new Set(Object.keys(collaboration.roles));
  const spaceIds = new Set(Object.keys(collaboration.spaces));

  for (const [botId, bot] of Object.entries(collaboration.bots)) {
    if (!agentIds.has(bot.agentId)) {
      pushIssue(issues, `collaboration.bots.${botId}.agentId`, `agent not found: "${bot.agentId}"`);
    }
    if (!slackAccountIds.has(bot.slackAccountId)) {
      pushIssue(
        issues,
        `collaboration.bots.${botId}.slackAccountId`,
        `Slack account not found: "${bot.slackAccountId}"`,
      );
    }
    if (!roleIds.has(bot.role)) {
      pushIssue(issues, `collaboration.bots.${botId}.role`, `role not found: "${bot.role}"`);
    }
    for (const allowedSpaceId of bot.allowedSpaces ?? []) {
      if (!spaceIds.has(allowedSpaceId)) {
        pushIssue(
          issues,
          `collaboration.bots.${botId}.allowedSpaces`,
          `space not found: "${allowedSpaceId}"`,
        );
      }
    }
  }

  for (const [roleId, role] of Object.entries(collaboration.roles)) {
    if (!agentIds.has(role.defaultAgentId)) {
      pushIssue(
        issues,
        `collaboration.roles.${roleId}.defaultAgentId`,
        `agent not found: "${role.defaultAgentId}"`,
      );
    }
    if (!botIds.has(role.defaultBotId)) {
      pushIssue(
        issues,
        `collaboration.roles.${roleId}.defaultBotId`,
        `bot not found: "${role.defaultBotId}"`,
      );
      continue;
    }
    const defaultBot = collaboration.bots[role.defaultBotId];
    if (defaultBot && defaultBot.role !== roleId) {
      pushIssue(
        issues,
        `collaboration.roles.${roleId}.defaultBotId`,
        `defaultBotId must reference a bot with role "${roleId}"`,
      );
    }
  }

  for (const [spaceId, space] of Object.entries(collaboration.spaces)) {
    if (space.ownerRole && !roleIds.has(space.ownerRole)) {
      pushIssue(
        issues,
        `collaboration.spaces.${spaceId}.ownerRole`,
        `role not found: "${space.ownerRole}"`,
      );
    }
    for (const memberRole of space.memberRoles ?? []) {
      if (!roleIds.has(memberRole)) {
        pushIssue(
          issues,
          `collaboration.spaces.${spaceId}.memberRoles`,
          `role not found: "${memberRole}"`,
        );
      }
    }
    for (const readableRole of space.memory?.readableByRoles ?? []) {
      if (!roleIds.has(readableRole)) {
        pushIssue(
          issues,
          `collaboration.spaces.${spaceId}.memory.readableByRoles`,
          `role not found: "${readableRole}"`,
        );
      }
    }
    for (const writableRole of space.memory?.writableByRoles ?? []) {
      if (!roleIds.has(writableRole)) {
        pushIssue(
          issues,
          `collaboration.spaces.${spaceId}.memory.writableByRoles`,
          `role not found: "${writableRole}"`,
        );
      }
    }
    const memberRoles = new Set(space.memberRoles ?? []);
    for (const targetRole of space.handoffs?.allowedTargets ?? []) {
      if (!roleIds.has(targetRole)) {
        pushIssue(
          issues,
          `collaboration.spaces.${spaceId}.handoffs.allowedTargets`,
          `role not found: "${targetRole}"`,
        );
        continue;
      }
      if (memberRoles.size > 0 && !memberRoles.has(targetRole)) {
        pushIssue(
          issues,
          `collaboration.spaces.${spaceId}.handoffs.allowedTargets`,
          `handoff target "${targetRole}" must be included in memberRoles`,
        );
      }
    }
    for (const destination of space.schedules?.defaultDestinations ?? []) {
      if (destination.kind === "space_default" && !spaceIds.has(destination.spaceId)) {
        pushIssue(
          issues,
          `collaboration.spaces.${spaceId}.schedules.defaultDestinations`,
          `space not found: "${destination.spaceId}"`,
        );
      }
      if (destination.kind === "slack_dm") {
        if (destination.identityId && !identityIds.has(destination.identityId)) {
          pushIssue(
            issues,
            `collaboration.spaces.${spaceId}.schedules.defaultDestinations`,
            `identity not found: "${destination.identityId}"`,
          );
        }
        if (destination.roleId && !roleIds.has(destination.roleId)) {
          pushIssue(
            issues,
            `collaboration.spaces.${spaceId}.schedules.defaultDestinations`,
            `role not found: "${destination.roleId}"`,
          );
        }
      }
    }
  }

  for (const job of collaboration.schedules?.jobs ?? []) {
    if (job.audience.kind === "identity" && !identityIds.has(job.audience.id)) {
      pushIssue(
        issues,
        `collaboration.schedules.jobs.${job.id}.audience.id`,
        `identity not found: "${job.audience.id}"`,
      );
    }
    if (job.audience.kind === "role" && !roleIds.has(job.audience.id)) {
      pushIssue(
        issues,
        `collaboration.schedules.jobs.${job.id}.audience.id`,
        `role not found: "${job.audience.id}"`,
      );
    }
    if (job.audience.kind === "space" && !spaceIds.has(job.audience.id)) {
      pushIssue(
        issues,
        `collaboration.schedules.jobs.${job.id}.audience.id`,
        `space not found: "${job.audience.id}"`,
      );
    }
    if (job.ownerRole && !roleIds.has(job.ownerRole)) {
      pushIssue(
        issues,
        `collaboration.schedules.jobs.${job.id}.ownerRole`,
        `role not found: "${job.ownerRole}"`,
      );
    }
    for (const sourceSpaceId of job.sourceSpaces) {
      if (!spaceIds.has(sourceSpaceId)) {
        pushIssue(
          issues,
          `collaboration.schedules.jobs.${job.id}.sourceSpaces`,
          `space not found: "${sourceSpaceId}"`,
        );
      }
    }
    for (const target of job.delivery) {
      if (target.kind === "space_default" && !spaceIds.has(target.spaceId)) {
        pushIssue(
          issues,
          `collaboration.schedules.jobs.${job.id}.delivery`,
          `space not found: "${target.spaceId}"`,
        );
      }
      if (target.kind === "slack_dm") {
        if (target.identityId && !identityIds.has(target.identityId)) {
          pushIssue(
            issues,
            `collaboration.schedules.jobs.${job.id}.delivery`,
            `identity not found: "${target.identityId}"`,
          );
        }
        if (target.roleId && !roleIds.has(target.roleId)) {
          pushIssue(
            issues,
            `collaboration.schedules.jobs.${job.id}.delivery`,
            `role not found: "${target.roleId}"`,
          );
        }
      }
    }
  }

  for (const [policyId, policy] of Object.entries(collaboration.approvals?.policies ?? {})) {
    for (const approverRole of policy.approverRoles) {
      if (!roleIds.has(approverRole)) {
        pushIssue(
          issues,
          `collaboration.approvals.policies.${policyId}.approverRoles`,
          `role not found: "${approverRole}"`,
        );
      }
    }
    for (const spaceId of policy.spaceFilter ?? []) {
      if (!spaceIds.has(spaceId)) {
        pushIssue(
          issues,
          `collaboration.approvals.policies.${policyId}.spaceFilter`,
          `space not found: "${spaceId}"`,
        );
      }
    }
  }

  return issues;
}
