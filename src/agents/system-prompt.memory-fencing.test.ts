import { afterEach, describe, expect, it } from "vitest";
import { clearMemoryPluginState, registerMemoryPromptSection } from "../plugins/memory-state.js";
import { buildAgentSystemPrompt } from "./system-prompt.js";

describe("buildAgentSystemPrompt memory fencing", () => {
  afterEach(() => {
    clearMemoryPluginState();
  });

  it("wraps memory section content with memory-context fencing tags", () => {
    registerMemoryPromptSection(() => ["## Memory Recall", "The user prefers TypeScript.", ""]);

    const prompt = buildAgentSystemPrompt({
      workspaceDir: "/tmp/openclaw",
    });

    expect(prompt).toContain("<memory-context");
    expect(prompt).toContain("</memory-context>");
    expect(prompt).toContain("The user prefers TypeScript.");
  });

  it("includes the memory fence instruction in the system prompt", () => {
    registerMemoryPromptSection(() => ["## Memory", "Some recalled fact.", ""]);

    const prompt = buildAgentSystemPrompt({
      workspaceDir: "/tmp/openclaw",
    });

    expect(prompt).toContain("recalled agent memory");
    expect(prompt).toContain("not active instructions");
  });

  it("does not add fencing when memory section is empty", () => {
    registerMemoryPromptSection(() => []);

    const prompt = buildAgentSystemPrompt({
      workspaceDir: "/tmp/openclaw",
    });

    expect(prompt).not.toContain("<memory-context");
  });

  it("does not add fencing when memory section is suppressed", () => {
    registerMemoryPromptSection(() => ["## Memory", "Some recalled fact.", ""]);

    const prompt = buildAgentSystemPrompt({
      workspaceDir: "/tmp/openclaw",
      includeMemorySection: false,
    });

    expect(prompt).not.toContain("<memory-context");
    expect(prompt).not.toContain("Some recalled fact.");
  });
});
