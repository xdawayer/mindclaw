import { describe, test, expect } from "vitest";
import { buildOnboardingPlan, type OnboardingInput } from "./onboarding-flow.js";

function makeInput(overrides?: Partial<OnboardingInput>): OnboardingInput {
  return {
    userId: "user-001",
    userName: "张三",
    department: "工程部",
    jobTitle: "高级工程师",
    hasExistingPreferences: false,
    ...overrides,
  };
}

describe("onboarding-flow", () => {
  describe("buildOnboardingPlan", () => {
    test("resolves role from job title", () => {
      const plan = buildOnboardingPlan(makeInput({ jobTitle: "产品经理" }));
      expect(plan.resolvedRole).toBe("pm");
    });

    test("resolves team from department", () => {
      const plan = buildOnboardingPlan(makeInput({ department: "销售部" }));
      expect(plan.resolvedTeam).toBe("sales");
    });

    test("marks needsWelcomeCard true for new users", () => {
      const plan = buildOnboardingPlan(makeInput({ hasExistingPreferences: false }));
      expect(plan.needsWelcomeCard).toBe(true);
    });

    test("marks needsWelcomeCard false when user already has preferences", () => {
      const plan = buildOnboardingPlan(makeInput({ hasExistingPreferences: true }));
      expect(plan.needsWelcomeCard).toBe(false);
    });

    test("generates default preferences based on resolved role", () => {
      const plan = buildOnboardingPlan(makeInput({ jobTitle: "销售总监" }));
      expect(plan.defaultPreferences).toBeDefined();
      expect(plan.defaultPreferences.language).toBe("zh-CN");
    });

    test("includes steps array with correct full sequence per design doc", () => {
      const plan = buildOnboardingPlan(makeInput());
      expect(plan.steps).toContain("resolve-role");
      expect(plan.steps).toContain("resolve-team");
      expect(plan.steps).toContain("init-preferences");
      expect(plan.steps).toContain("send-welcome-card");
      expect(plan.steps).toContain("write-onboarding-memory");

      // resolve-role should come before init-preferences
      const roleIdx = plan.steps.indexOf("resolve-role");
      const prefsIdx = plan.steps.indexOf("init-preferences");
      expect(roleIdx).toBeLessThan(prefsIdx);

      // write-onboarding-memory should be last
      const memIdx = plan.steps.indexOf("write-onboarding-memory");
      expect(memIdx).toBe(plan.steps.length - 1);
    });

    test("skips send-welcome-card and write-onboarding-memory when user has existing preferences", () => {
      const plan = buildOnboardingPlan(makeInput({ hasExistingPreferences: true }));
      expect(plan.steps).not.toContain("send-welcome-card");
      expect(plan.steps).not.toContain("write-onboarding-memory");
    });

    test("falls back to default role when job title unrecognized", () => {
      const plan = buildOnboardingPlan(makeInput({ jobTitle: "CEO", department: "总裁办" }));
      expect(plan.resolvedRole).toBe("default");
    });

    test("maps engineering department variants correctly", () => {
      const plan1 = buildOnboardingPlan(makeInput({ department: "Engineering" }));
      expect(plan1.resolvedTeam).toBe("engineering");

      const plan2 = buildOnboardingPlan(makeInput({ department: "技术部" }));
      expect(plan2.resolvedTeam).toBe("engineering");
    });
  });
});
