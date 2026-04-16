import { describe, test, expect } from "vitest";
import {
  shouldAskForConfirmation,
  selectTopCandidates,
  type RoutingCandidate,
} from "./confidence-gate.js";

function makeCandidate(id: string, confidence: number): RoutingCandidate {
  return { agentId: id, confidence, label: id };
}

describe("confidence-gate", () => {
  describe("shouldAskForConfirmation", () => {
    test("returns false when confidence >= threshold", () => {
      expect(shouldAskForConfirmation(0.8, 0.7)).toBe(false);
    });

    test("returns true when confidence < threshold", () => {
      expect(shouldAskForConfirmation(0.5, 0.7)).toBe(true);
    });

    test("returns false when confidence equals threshold exactly", () => {
      expect(shouldAskForConfirmation(0.7, 0.7)).toBe(false);
    });

    test("uses default threshold of 0.7 when not specified", () => {
      expect(shouldAskForConfirmation(0.6)).toBe(true);
      expect(shouldAskForConfirmation(0.7)).toBe(false);
    });
  });

  describe("selectTopCandidates", () => {
    test("returns top N candidates sorted by confidence descending", () => {
      const candidates = [
        makeCandidate("a", 0.3),
        makeCandidate("b", 0.9),
        makeCandidate("c", 0.6),
        makeCandidate("d", 0.8),
      ];

      const top = selectTopCandidates(candidates, 3);
      expect(top.map((c) => c.agentId)).toEqual(["b", "d", "c"]);
    });

    test("returns all candidates when N > length", () => {
      const candidates = [makeCandidate("a", 0.5), makeCandidate("b", 0.9)];
      const top = selectTopCandidates(candidates, 5);
      expect(top).toHaveLength(2);
      expect(top[0].agentId).toBe("b");
    });

    test("returns empty array for empty input", () => {
      expect(selectTopCandidates([], 3)).toEqual([]);
    });

    test("defaults to top 3", () => {
      const candidates = [
        makeCandidate("a", 0.1),
        makeCandidate("b", 0.2),
        makeCandidate("c", 0.3),
        makeCandidate("d", 0.4),
        makeCandidate("e", 0.5),
      ];

      const top = selectTopCandidates(candidates);
      expect(top).toHaveLength(3);
    });
  });
});
