const VALID_SKILL_ID = /^[a-z0-9]([a-z0-9-]*[a-z0-9])?$/;
const MAX_LENGTH = 64;

export type SkillIdValidation = { valid: true } | { valid: false; reason: string };

export function validateSkillId(id: string): SkillIdValidation {
  if (id.length === 0) {
    return { valid: false, reason: "Skill ID cannot be empty" };
  }

  if (id.length > MAX_LENGTH) {
    return { valid: false, reason: `Skill ID must be at most ${MAX_LENGTH} characters` };
  }

  if (!VALID_SKILL_ID.test(id)) {
    return {
      valid: false,
      reason:
        "Skill ID must contain only lowercase letters, numbers, and hyphens (no invalid character allowed)",
    };
  }

  return { valid: true };
}
