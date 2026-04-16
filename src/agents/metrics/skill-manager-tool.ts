import { SkillManager } from "./skill-manager.js";

export type SkillManagerToolInput = {
  action: string;
  skillId?: string;
  name?: string;
  description?: string;
  content?: string;
};

export type SkillManagerToolDef = {
  name: string;
  description: string;
  execute: (input: SkillManagerToolInput) => Promise<string>;
};

export function createSkillManagerTool(workspaceDir: string): SkillManagerToolDef {
  const manager = new SkillManager(workspaceDir);

  return {
    name: "skill_manager",
    description:
      "Propose, list, or delete draft skills. " +
      "Drafts must be approved by a human before activation. " +
      "Actions: propose, list-drafts, delete-draft.",

    async execute(input: SkillManagerToolInput): Promise<string> {
      switch (input.action) {
        case "propose": {
          if (!input.skillId || !input.name || !input.description || !input.content) {
            return JSON.stringify({
              ok: false,
              error: "propose requires skillId, name, description, and content",
            });
          }
          const result = await manager.propose({
            skillId: input.skillId,
            name: input.name,
            description: input.description,
            content: input.content,
          });
          return JSON.stringify(result);
        }

        case "list-drafts": {
          const drafts = await manager.listDrafts();
          return JSON.stringify(drafts);
        }

        case "delete-draft": {
          if (!input.skillId) {
            return JSON.stringify({ ok: false, error: "delete-draft requires skillId" });
          }
          const result = await manager.deleteDraft(input.skillId);
          return JSON.stringify(result);
        }

        default:
          return JSON.stringify({
            ok: false,
            error: `Unknown action: ${input.action}. Valid actions: propose, list-drafts, delete-draft`,
          });
      }
    },
  };
}
