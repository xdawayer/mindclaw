import fs from "node:fs/promises";
import path from "node:path";
import { sanitizeUserId } from "./sanitize-user-id.js";

export type UserPreferences = {
  language: string;
  responseStyle: "concise" | "detailed" | "auto";
  preferredAgentId?: string;
  notificationsEnabled: boolean;
  customInstructions?: string;
};

export type UserPreferencesParams = {
  workspaceDir: string;
  userId: string;
};

const VALID_RESPONSE_STYLES = new Set(["concise", "detailed", "auto"]);
const MAX_CUSTOM_INSTRUCTIONS_LEN = 500;
const LANGUAGE_RE = /^[a-z]{2}(-[A-Z]{2})?$/;
const PREFS_FILENAME = "preferences.json";

const PREFERENCES_KEYS = new Set<string>([
  "language",
  "responseStyle",
  "preferredAgentId",
  "notificationsEnabled",
  "customInstructions",
]);

function resolvePrefsPath(params: UserPreferencesParams): string {
  const safe = sanitizeUserId(params.userId);
  return path.join(params.workspaceDir, "memory", "users", safe, PREFS_FILENAME);
}

export function getDefaultPreferences(): UserPreferences {
  return {
    language: "zh-CN",
    responseStyle: "auto",
    notificationsEnabled: true,
  };
}

export function validatePreferences(partial: Partial<UserPreferences>): string[] {
  const errors: string[] = [];
  if (partial.language !== undefined && !LANGUAGE_RE.test(partial.language)) {
    errors.push("language: invalid format, expected e.g. 'en-US' or 'zh-CN'");
  }
  if (partial.responseStyle !== undefined && !VALID_RESPONSE_STYLES.has(partial.responseStyle)) {
    errors.push("responseStyle: must be 'concise', 'detailed', or 'auto'");
  }
  if (
    partial.customInstructions !== undefined &&
    partial.customInstructions.length > MAX_CUSTOM_INSTRUCTIONS_LEN
  ) {
    errors.push(`customInstructions: must be ${MAX_CUSTOM_INSTRUCTIONS_LEN} characters or fewer`);
  }
  return errors;
}

export function mergePreferences(
  defaults: UserPreferences,
  overrides: Partial<UserPreferences>,
): UserPreferences {
  const merged = { ...defaults };
  for (const [key, value] of Object.entries(overrides)) {
    if (value !== undefined) {
      (merged as Record<string, unknown>)[key] = value;
    }
  }
  return merged;
}

function pickKnownKeys(obj: Record<string, unknown>): Partial<UserPreferences> {
  const picked: Record<string, unknown> = {};
  for (const key of PREFERENCES_KEYS) {
    if (key in obj) {
      picked[key] = obj[key];
    }
  }
  return picked as Partial<UserPreferences>;
}

export async function loadUserPreferences(params: UserPreferencesParams): Promise<UserPreferences> {
  try {
    const raw = await fs.readFile(resolvePrefsPath(params), "utf-8");
    const parsed = JSON.parse(raw) as Record<string, unknown>;
    const picked = pickKnownKeys(parsed);
    const errors = validatePreferences(picked);
    if (errors.length > 0) {
      return getDefaultPreferences();
    }
    return mergePreferences(getDefaultPreferences(), picked);
  } catch {
    return getDefaultPreferences();
  }
}

export async function saveUserPreferences(
  params: UserPreferencesParams,
  prefs: UserPreferences,
): Promise<void> {
  const filePath = resolvePrefsPath(params);
  await fs.mkdir(path.dirname(filePath), { recursive: true });
  await fs.writeFile(filePath, JSON.stringify(prefs, null, 2), "utf-8");
}
