import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { createSkillManagerTool } from "./skill-manager-tool.js";

let workspaceDir: string;

beforeEach(async () => {
  workspaceDir = await fs.mkdtemp(path.join(os.tmpdir(), "openclaw-skill-tool-"));
});

afterEach(async () => {
  await fs.rm(workspaceDir, { recursive: true, force: true });
});

describe("createSkillManagerTool", () => {
  it("returns a tool with the expected name and description", () => {
    const tool = createSkillManagerTool(workspaceDir);

    expect(tool.name).toBe("skill_manager");
    expect(tool.description).toContain("skill");
  });

  it("propose action creates a draft skill", async () => {
    const tool = createSkillManagerTool(workspaceDir);

    const result = await tool.execute({
      action: "propose",
      skillId: "my-helper",
      name: "My Helper",
      description: "Helps with stuff",
      content: "## Steps\n1. Do the thing",
    });

    expect(result).toBeDefined();
    const text = typeof result === "string" ? result : JSON.stringify(result);
    expect(text).toContain("ok");

    // Verify the draft was actually created
    const draftPath = path.join(workspaceDir, "skills", ".drafts", "my-helper", "SKILL.md");
    const content = await fs.readFile(draftPath, "utf-8");
    expect(content).toContain("My Helper");
  });

  it("list-drafts action returns empty array when no drafts", async () => {
    const tool = createSkillManagerTool(workspaceDir);

    const result = await tool.execute({ action: "list-drafts" });

    const text = typeof result === "string" ? result : JSON.stringify(result);
    expect(text).toContain("[]");
  });

  it("delete-draft action removes a draft", async () => {
    const tool = createSkillManagerTool(workspaceDir);

    await tool.execute({
      action: "propose",
      skillId: "temp-skill",
      name: "Temp",
      description: "Temporary",
      content: "temp content",
    });

    const deleteResult = await tool.execute({
      action: "delete-draft",
      skillId: "temp-skill",
    });

    const text = typeof deleteResult === "string" ? deleteResult : JSON.stringify(deleteResult);
    expect(text).toContain("ok");
  });

  it("rejects unknown actions", async () => {
    const tool = createSkillManagerTool(workspaceDir);

    const result = await tool.execute({ action: "invalid-action" });

    const text = typeof result === "string" ? result : JSON.stringify(result);
    expect(text).toContain("error");
  });
});
