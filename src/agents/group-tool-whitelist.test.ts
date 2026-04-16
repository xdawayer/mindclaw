import { describe, expect, it } from "vitest";
import {
  resolveGroupAllowedTools,
  DEFAULT_GROUP_SAFE_TOOLS,
  type GroupToolPolicy,
} from "./group-tool-whitelist.js";

describe("group-tool-whitelist", () => {
  describe("DEFAULT_GROUP_SAFE_TOOLS", () => {
    it("includes search as a safe default", () => {
      expect(DEFAULT_GROUP_SAFE_TOOLS).toContain("search");
    });

    it("does not include dangerous tools", () => {
      expect(DEFAULT_GROUP_SAFE_TOOLS).not.toContain("exec");
      expect(DEFAULT_GROUP_SAFE_TOOLS).not.toContain("bash");
      expect(DEFAULT_GROUP_SAFE_TOOLS).not.toContain("database");
    });
  });

  describe("resolveGroupAllowedTools", () => {
    it("returns default safe tools when no policy exists for the group", () => {
      const result = resolveGroupAllowedTools("unknown-group", []);
      expect(result).toEqual(DEFAULT_GROUP_SAFE_TOOLS);
    });

    it("returns policy-defined tools when a matching policy exists", () => {
      const policies: GroupToolPolicy[] = [
        { groupId: "eng-chat", allowedTools: ["search", "git", "exec"] },
      ];
      const result = resolveGroupAllowedTools("eng-chat", policies);
      expect(result).toEqual(["search", "git", "exec"]);
    });

    it("matches case-insensitively on groupId", () => {
      const policies: GroupToolPolicy[] = [
        { groupId: "Eng-Chat", allowedTools: ["search", "git"] },
      ];
      const result = resolveGroupAllowedTools("eng-chat", policies);
      expect(result).toEqual(["search", "git"]);
    });

    it("uses first matching policy when multiple match", () => {
      const policies: GroupToolPolicy[] = [
        { groupId: "eng-chat", allowedTools: ["search", "git"] },
        { groupId: "eng-chat", allowedTools: ["search", "exec", "bash"] },
      ];
      const result = resolveGroupAllowedTools("eng-chat", policies);
      expect(result).toEqual(["search", "git"]);
    });

    it("always includes search even if policy omits it", () => {
      const policies: GroupToolPolicy[] = [{ groupId: "test-group", allowedTools: ["doc-gen"] }];
      const result = resolveGroupAllowedTools("test-group", policies);
      expect(result).toContain("search");
      expect(result).toContain("doc-gen");
    });
  });
});
