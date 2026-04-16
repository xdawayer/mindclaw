import fs from "node:fs/promises";
import path from "node:path";
import { scanMemoryContent } from "./memory-safety.js";
import { validateSkillId } from "./skill-id-validator.js";

const MAX_CONTENT_LENGTH = 100_000;

function sanitizeYamlValue(value: string): string {
  // Strip newlines and carriage returns to prevent YAML injection
  const singleLine = value.replace(/[\r\n]+/g, " ").trim();
  // Quote if value contains YAML-special characters
  if (/[:"'{}[\]#|>&*!%@`]/.test(singleLine)) {
    return `"${singleLine.replace(/\\/g, "\\\\").replace(/"/g, '\\"')}"`;
  }
  return singleLine;
}

export type SkillManagerResult = { ok: true } | { ok: false; error: string };

export type SkillDraftEntry = {
  skillId: string;
  name: string;
  description: string;
};

export class SkillManager {
  private draftsDir: string;
  private activeDir: string;

  constructor(workspaceDir: string) {
    this.draftsDir = path.join(workspaceDir, "skills", ".drafts");
    this.activeDir = path.join(workspaceDir, "skills");
  }

  async propose(params: {
    skillId: string;
    name: string;
    description: string;
    content: string;
  }): Promise<SkillManagerResult> {
    const validation = validateSkillId(params.skillId);
    if (!validation.valid) {
      return { ok: false, error: validation.reason };
    }

    if (params.content.length > MAX_CONTENT_LENGTH) {
      return {
        ok: false,
        error: `Content exceeds maximum length of ${MAX_CONTENT_LENGTH} characters`,
      };
    }

    const safety = scanMemoryContent(params.content);
    if (!safety.safe) {
      const details = safety.violations.map((v) => v.detail).join(", ");
      return { ok: false, error: `Content failed safety scan: ${details}` };
    }

    const skillDir = path.join(this.draftsDir, params.skillId);
    await fs.mkdir(skillDir, { recursive: true });

    const safeName = sanitizeYamlValue(params.name);
    const safeDesc = sanitizeYamlValue(params.description);

    const frontmatter = [
      "---",
      `name: ${safeName}`,
      `description: ${safeDesc}`,
      "---",
      "",
      params.content,
    ].join("\n");

    await fs.writeFile(path.join(skillDir, "SKILL.md"), frontmatter, "utf-8");
    return { ok: true };
  }

  async listDrafts(): Promise<SkillDraftEntry[]> {
    try {
      const entries = await fs.readdir(this.draftsDir, { withFileTypes: true });
      const drafts: SkillDraftEntry[] = [];

      for (const entry of entries) {
        if (!entry.isDirectory()) {
          continue;
        }
        const skillFile = path.join(this.draftsDir, entry.name, "SKILL.md");
        try {
          const content = await fs.readFile(skillFile, "utf-8");
          const name = content.match(/^name:\s*(.+)$/m)?.[1] ?? entry.name;
          const description = content.match(/^description:\s*(.+)$/m)?.[1] ?? "";
          drafts.push({ skillId: entry.name, name, description });
        } catch {
          // Skip drafts without valid SKILL.md
        }
      }

      return drafts;
    } catch {
      return [];
    }
  }

  async deleteDraft(skillId: string): Promise<SkillManagerResult> {
    const validation = validateSkillId(skillId);
    if (!validation.valid) {
      return { ok: false, error: validation.reason };
    }

    const draftDir = path.join(this.draftsDir, skillId);
    try {
      await fs.access(draftDir);
    } catch {
      return { ok: false, error: `Draft "${skillId}" not found` };
    }

    await fs.rm(draftDir, { recursive: true, force: true });
    return { ok: true };
  }

  async approve(skillId: string): Promise<SkillManagerResult> {
    const validation = validateSkillId(skillId);
    if (!validation.valid) {
      return { ok: false, error: validation.reason };
    }

    const draftDir = path.join(this.draftsDir, skillId);
    try {
      await fs.access(draftDir);
    } catch {
      return { ok: false, error: `Draft "${skillId}" not found` };
    }

    const targetDir = path.join(this.activeDir, skillId);
    await fs.mkdir(targetDir, { recursive: true });

    // Copy SKILL.md from draft to active
    const src = path.join(draftDir, "SKILL.md");
    const dest = path.join(targetDir, "SKILL.md");
    await fs.copyFile(src, dest);

    // Remove draft
    await fs.rm(draftDir, { recursive: true, force: true });
    return { ok: true };
  }
}
