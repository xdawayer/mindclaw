import { describe, expect, it } from "vitest";
import { classifySessionOutcome } from "./outcome-classifier.js";
import type { SessionOutcome, SessionOutcomeInput } from "./outcome-classifier.js";

describe("classifySessionOutcome", () => {
  function input(overrides: Partial<SessionOutcomeInput> = {}): SessionOutcomeInput {
    return {
      messageCount: 4,
      stopReason: "end_turn",
      aborted: false,
      errorOccurred: false,
      durationMs: 5000,
      ...overrides,
    };
  }

  describe("success", () => {
    it("classifies a normal completed session as success", () => {
      const result = classifySessionOutcome(input());
      expect(result).toBe("success" satisfies SessionOutcome);
    });

    it("classifies session with many turns as success when completed normally", () => {
      const result = classifySessionOutcome(input({ messageCount: 20 }));
      expect(result).toBe("success");
    });
  });

  describe("fail", () => {
    it("classifies session with error as fail", () => {
      const result = classifySessionOutcome(input({ errorOccurred: true }));
      expect(result).toBe("fail" satisfies SessionOutcome);
    });

    it("classifies session with non-end_turn stopReason as fail", () => {
      const result = classifySessionOutcome(input({ stopReason: "max_tokens" }));
      expect(result).toBe("fail");
    });

    it("classifies aborted session as fail", () => {
      const result = classifySessionOutcome(input({ aborted: true }));
      expect(result).toBe("fail");
    });
  });

  describe("unknown", () => {
    it("classifies session with fewer than 2 messages as unknown", () => {
      const result = classifySessionOutcome(input({ messageCount: 1 }));
      expect(result).toBe("unknown" satisfies SessionOutcome);
    });

    it("classifies session with 0 messages as unknown", () => {
      const result = classifySessionOutcome(input({ messageCount: 0 }));
      expect(result).toBe("unknown");
    });
  });

  describe("partial", () => {
    it("classifies session with stopReason 'length' as partial", () => {
      const result = classifySessionOutcome(input({ stopReason: "length" }));
      expect(result).toBe("partial" satisfies SessionOutcome);
    });
  });

  describe("edge cases", () => {
    it("handles missing stopReason gracefully", () => {
      const result = classifySessionOutcome(input({ stopReason: undefined, messageCount: 4 }));
      expect(result).toBe("success");
    });

    it("error takes precedence over low message count", () => {
      const result = classifySessionOutcome(input({ errorOccurred: true, messageCount: 1 }));
      expect(result).toBe("fail");
    });

    it("abort takes precedence over normal stopReason", () => {
      const result = classifySessionOutcome(input({ aborted: true, stopReason: "end_turn" }));
      expect(result).toBe("fail");
    });
  });
});
