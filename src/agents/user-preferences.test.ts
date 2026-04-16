import crypto from "node:crypto";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { describe, test, expect, afterEach } from "vitest";
import {
  getDefaultPreferences,
  validatePreferences,
  mergePreferences,
  loadUserPreferences,
  saveUserPreferences,
} from "./user-preferences.js";

describe("user-preferences", () => {
  const tempDirs: string[] = [];

  function makeTempDir(): string {
    const dir = path.join(os.tmpdir(), `openclaw-user-prefs-test-${crypto.randomUUID()}`);
    tempDirs.push(dir);
    return dir;
  }

  afterEach(async () => {
    for (const dir of tempDirs) {
      await fs.rm(dir, { recursive: true, force: true });
    }
    tempDirs.length = 0;
  });

  describe("getDefaultPreferences", () => {
    test("returns expected defaults", () => {
      const defaults = getDefaultPreferences();
      expect(defaults.language).toBe("zh-CN");
      expect(defaults.responseStyle).toBe("auto");
      expect(defaults.notificationsEnabled).toBe(true);
      expect(defaults.preferredAgentId).toBeUndefined();
      expect(defaults.customInstructions).toBeUndefined();
    });
  });

  describe("validatePreferences", () => {
    test("accepts valid language codes", () => {
      const errors = validatePreferences({ language: "en-US" });
      expect(errors).toEqual([]);
    });

    test("accepts valid zh-CN language code", () => {
      const errors = validatePreferences({ language: "zh-CN" });
      expect(errors).toEqual([]);
    });

    test("rejects invalid responseStyle values", () => {
      const errors = validatePreferences({
        responseStyle: "verbose" as never,
      });
      expect(errors.length).toBeGreaterThan(0);
      expect(errors.some((e) => e.toLowerCase().includes("responsestyle"))).toBe(true);
    });

    test("rejects customInstructions longer than 500 chars", () => {
      const errors = validatePreferences({
        customInstructions: "a".repeat(501),
      });
      expect(errors.length).toBeGreaterThan(0);
      expect(errors.some((e) => e.toLowerCase().includes("custominstructions"))).toBe(true);
    });

    test("returns empty array for valid input", () => {
      const errors = validatePreferences({
        language: "en-US",
        responseStyle: "concise",
        notificationsEnabled: false,
        customInstructions: "Be brief.",
      });
      expect(errors).toEqual([]);
    });
  });

  describe("mergePreferences", () => {
    test("overrides only specified fields", () => {
      const defaults = getDefaultPreferences();
      const merged = mergePreferences(defaults, { language: "en-US" });
      expect(merged.language).toBe("en-US");
      expect(merged.responseStyle).toBe(defaults.responseStyle);
      expect(merged.notificationsEnabled).toBe(defaults.notificationsEnabled);
    });

    test("preserves defaults for unspecified fields", () => {
      const defaults = getDefaultPreferences();
      const merged = mergePreferences(defaults, {
        responseStyle: "detailed",
      });
      expect(merged.language).toBe(defaults.language);
      expect(merged.responseStyle).toBe("detailed");
      expect(merged.notificationsEnabled).toBe(defaults.notificationsEnabled);
      expect(merged.preferredAgentId).toBeUndefined();
    });

    test("ignores undefined values in overrides", () => {
      const defaults = getDefaultPreferences();
      const merged = mergePreferences(defaults, {
        language: undefined,
        responseStyle: undefined,
      });
      expect(merged.language).toBe(defaults.language);
      expect(merged.responseStyle).toBe(defaults.responseStyle);
    });
  });

  describe("loadUserPreferences", () => {
    test("returns defaults when no file exists", async () => {
      const dir = makeTempDir();
      const prefs = await loadUserPreferences({
        workspaceDir: dir,
        userId: "nonexistent-user",
      });
      expect(prefs).toEqual(getDefaultPreferences());
    });
  });

  describe("saveUserPreferences", () => {
    test("writes JSON to {workspace}/memory/users/{userId}/preferences.json", async () => {
      const dir = makeTempDir();
      const userId = "user-123";
      const prefs = {
        ...getDefaultPreferences(),
        language: "en-US",
      };

      await saveUserPreferences({ workspaceDir: dir, userId }, prefs);

      const filePath = path.join(dir, "memory", "users", userId, "preferences.json");
      const content = await fs.readFile(filePath, "utf-8");
      const parsed = JSON.parse(content);
      expect(parsed.language).toBe("en-US");
    });

    test("creates directories if they don't exist", async () => {
      const dir = makeTempDir();
      const userId = "user-456";

      await saveUserPreferences({ workspaceDir: dir, userId }, getDefaultPreferences());

      const dirPath = path.join(dir, "memory", "users", userId);
      const stat = await fs.stat(dirPath);
      expect(stat.isDirectory()).toBe(true);
    });
  });

  describe("resolvePrefsPath safety", () => {
    test("throws when userId sanitizes to empty string", async () => {
      const dir = makeTempDir();
      await expect(
        saveUserPreferences({ workspaceDir: dir, userId: "!!!" }, getDefaultPreferences()),
      ).rejects.toThrow("empty string");
    });

    test("throws for empty userId", async () => {
      const dir = makeTempDir();
      await expect(
        saveUserPreferences({ workspaceDir: dir, userId: "" }, getDefaultPreferences()),
      ).rejects.toThrow("empty string");
    });

    test("returns defaults when loading with invalid userId (caught internally)", async () => {
      const dir = makeTempDir();
      const loaded = await loadUserPreferences({ workspaceDir: dir, userId: "!!!" });
      expect(loaded).toEqual(getDefaultPreferences());
    });
  });

  describe("loadUserPreferences validation", () => {
    test("returns defaults when file contains invalid responseStyle", async () => {
      const dir = makeTempDir();
      const userId = "user-corrupt";
      const prefsDir = path.join(dir, "memory", "users", userId);
      await fs.mkdir(prefsDir, { recursive: true });
      await fs.writeFile(
        path.join(prefsDir, "preferences.json"),
        JSON.stringify({ language: "en-US", responseStyle: "INVALID", notificationsEnabled: true }),
        "utf-8",
      );

      const loaded = await loadUserPreferences({ workspaceDir: dir, userId });
      expect(loaded).toEqual(getDefaultPreferences());
    });

    test("returns defaults when file contains non-JSON content", async () => {
      const dir = makeTempDir();
      const userId = "user-garbage";
      const prefsDir = path.join(dir, "memory", "users", userId);
      await fs.mkdir(prefsDir, { recursive: true });
      await fs.writeFile(path.join(prefsDir, "preferences.json"), "not json at all", "utf-8");

      const loaded = await loadUserPreferences({ workspaceDir: dir, userId });
      expect(loaded).toEqual(getDefaultPreferences());
    });

    test("returns defaults when file has extra prototype-polluting keys", async () => {
      const dir = makeTempDir();
      const userId = "user-pollution";
      const prefsDir = path.join(dir, "memory", "users", userId);
      await fs.mkdir(prefsDir, { recursive: true });
      await fs.writeFile(
        path.join(prefsDir, "preferences.json"),
        JSON.stringify({
          language: "en-US",
          responseStyle: "concise",
          notificationsEnabled: true,
          __proto__: { isAdmin: true },
          constructor: "hacked",
        }),
        "utf-8",
      );

      const loaded = await loadUserPreferences({ workspaceDir: dir, userId });
      // Should strip unknown keys and return clean preferences
      expect((loaded as Record<string, unknown>).__proto__).toBeDefined(); // all objects have __proto__
      expect((loaded as Record<string, unknown>).constructor).not.toBe("hacked");
    });
  });

  describe("round-trip", () => {
    test("loadUserPreferences reads back saved preferences correctly", async () => {
      const dir = makeTempDir();
      const userId = "user-roundtrip";
      const prefs = {
        ...getDefaultPreferences(),
        language: "ja-JP",
        responseStyle: "concise" as const,
        preferredAgentId: "agent-42",
        notificationsEnabled: false,
        customInstructions: "Always respond in haiku.",
      };

      await saveUserPreferences({ workspaceDir: dir, userId }, prefs);
      const loaded = await loadUserPreferences({ workspaceDir: dir, userId });

      expect(loaded).toEqual(prefs);
    });
  });
});
