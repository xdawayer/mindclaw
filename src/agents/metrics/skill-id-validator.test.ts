import { describe, expect, it } from "vitest";
import { validateSkillId } from "./skill-id-validator.js";

describe("validateSkillId", () => {
  describe("valid IDs", () => {
    it("accepts lowercase kebab-case", () => {
      expect(validateSkillId("my-skill")).toEqual({ valid: true });
    });

    it("accepts single word", () => {
      expect(validateSkillId("deploy")).toEqual({ valid: true });
    });

    it("accepts numbers", () => {
      expect(validateSkillId("task-v2")).toEqual({ valid: true });
    });

    it("accepts purely numeric parts", () => {
      expect(validateSkillId("step-3-done")).toEqual({ valid: true });
    });
  });

  describe("path traversal prevention", () => {
    it("rejects dots", () => {
      const result = validateSkillId("../etc/cron.d/evil");
      expect(result.valid).toBe(false);
      if (!result.valid) {
        expect(result.reason).toContain("character");
      }
    });

    it("rejects slashes", () => {
      const result = validateSkillId("foo/bar");
      expect(result.valid).toBe(false);
    });

    it("rejects backslashes", () => {
      const result = validateSkillId("foo\\bar");
      expect(result.valid).toBe(false);
    });

    it("rejects double dots", () => {
      const result = validateSkillId("..");
      expect(result.valid).toBe(false);
    });
  });

  describe("invalid characters", () => {
    it("rejects uppercase", () => {
      const result = validateSkillId("MySkill");
      expect(result.valid).toBe(false);
    });

    it("rejects spaces", () => {
      const result = validateSkillId("my skill");
      expect(result.valid).toBe(false);
    });

    it("rejects underscores", () => {
      const result = validateSkillId("my_skill");
      expect(result.valid).toBe(false);
    });

    it("rejects special characters", () => {
      const result = validateSkillId("skill@v2");
      expect(result.valid).toBe(false);
    });
  });

  describe("length limits", () => {
    it("rejects empty string", () => {
      const result = validateSkillId("");
      expect(result.valid).toBe(false);
    });

    it("rejects IDs longer than 64 characters", () => {
      const result = validateSkillId("a".repeat(65));
      expect(result.valid).toBe(false);
      if (!result.valid) {
        expect(result.reason).toContain("64");
      }
    });

    it("accepts ID at exactly 64 characters", () => {
      const result = validateSkillId("a".repeat(64));
      expect(result.valid).toBe(true);
    });
  });
});
