import { resolveRoleForUser } from "./role-templates.js";
import { getDefaultPreferences, type UserPreferences } from "./user-preferences.js";

export type OnboardingInput = {
  userId: string;
  userName: string;
  department: string;
  jobTitle: string;
  hasExistingPreferences: boolean;
};

export type OnboardingPlan = {
  resolvedRole: string;
  resolvedTeam: string;
  needsWelcomeCard: boolean;
  defaultPreferences: UserPreferences;
  steps: string[];
};

const DEPT_TO_TEAM: [RegExp, string][] = [
  [/工程|engineer|技术|dev/i, "engineering"],
  [/销售|sales|商务/i, "sales"],
  [/产品|product/i, "product"],
  [/运营|ops|operation/i, "operations"],
  [/hr|人力|人事/i, "hr"],
];

function resolveTeam(department: string): string {
  for (const [pattern, teamId] of DEPT_TO_TEAM) {
    if (pattern.test(department)) {
      return teamId;
    }
  }
  return "general";
}

export function buildOnboardingPlan(input: OnboardingInput): OnboardingPlan {
  const resolvedRole = resolveRoleForUser({
    jobTitle: input.jobTitle,
    department: input.department,
  });
  const resolvedTeam = resolveTeam(input.department);
  const needsWelcomeCard = !input.hasExistingPreferences;

  const steps: string[] = ["resolve-role", "resolve-team", "init-preferences"];
  if (needsWelcomeCard) {
    steps.push("send-welcome-card");
    steps.push("write-onboarding-memory");
  }

  return {
    resolvedRole,
    resolvedTeam,
    needsWelcomeCard,
    defaultPreferences: getDefaultPreferences(),
    steps,
  };
}
