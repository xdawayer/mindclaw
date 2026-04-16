import { describe, test, expect } from "vitest";
import { estimateTokens, allocateBudget, truncateToFit, DEFAULT_BUDGET } from "./context-budget.js";

describe("context-budget", () => {
  describe("estimateTokens", () => {
    test("estimates English text at ~4 chars per token", () => {
      const text = "Hello world, this is a test sentence.";
      const tokens = estimateTokens(text);
      // ~36 chars / 4 = ~9 tokens
      expect(tokens).toBeGreaterThanOrEqual(7);
      expect(tokens).toBeLessThanOrEqual(12);
    });

    test("estimates CJK text at ~1.5 chars per token", () => {
      const text = "你好世界这是一个测试句子";
      const tokens = estimateTokens(text);
      // 12 CJK chars / 1.5 = ~8 tokens
      expect(tokens).toBeGreaterThanOrEqual(6);
      expect(tokens).toBeLessThanOrEqual(12);
    });

    test("returns 0 for empty string", () => {
      expect(estimateTokens("")).toBe(0);
    });
  });

  describe("DEFAULT_BUDGET", () => {
    test("org budget is ~500", () => {
      expect(DEFAULT_BUDGET.org).toBe(500);
    });

    test("team budget is ~500", () => {
      expect(DEFAULT_BUDGET.team).toBe(500);
    });

    test("role budget is ~200", () => {
      expect(DEFAULT_BUDGET.role).toBe(200);
    });

    test("user budget is ~300", () => {
      expect(DEFAULT_BUDGET.user).toBe(300);
    });

    test("total does not exceed 1500", () => {
      const total =
        DEFAULT_BUDGET.org + DEFAULT_BUDGET.team + DEFAULT_BUDGET.role + DEFAULT_BUDGET.user;
      expect(total).toBeLessThanOrEqual(1500);
    });
  });

  describe("allocateBudget", () => {
    test("returns default budget when no overrides", () => {
      const budget = allocateBudget();
      expect(budget).toEqual(DEFAULT_BUDGET);
    });

    test("allows partial overrides within total limit", () => {
      const budget = allocateBudget({ org: 400 });
      expect(budget.org).toBe(400);
      expect(budget.team).toBe(DEFAULT_BUDGET.team);
    });

    test("overrides that push total over limit get scaled down", () => {
      const budget = allocateBudget({ org: 800 });
      const total = budget.org + budget.team + budget.role + budget.user;
      expect(total).toBeLessThanOrEqual(1500);
      // org should be largest since it started largest
      expect(budget.org).toBeGreaterThan(budget.team);
    });

    test("clamps total to maxTotal (default 1500)", () => {
      const budget = allocateBudget({ org: 1000, team: 1000 });
      const total = budget.org + budget.team + budget.role + budget.user;
      expect(total).toBeLessThanOrEqual(1500);
    });
  });

  describe("truncateToFit", () => {
    test("returns content unchanged when within budget", () => {
      const content = "Short content.";
      const result = truncateToFit(content, 100);
      expect(result).toBe(content);
    });

    test("truncates content that exceeds budget", () => {
      const content = "A".repeat(2000); // ~500 tokens
      const result = truncateToFit(content, 50);
      const resultTokens = estimateTokens(result);
      expect(resultTokens).toBeLessThanOrEqual(55); // small tolerance
    });

    test("returns empty string for 0 budget", () => {
      expect(truncateToFit("some content", 0)).toBe("");
    });

    test("handles CJK content", () => {
      const content = "中".repeat(500); // ~333 tokens
      const result = truncateToFit(content, 50);
      expect(result.length).toBeLessThan(content.length);
    });
  });
});
