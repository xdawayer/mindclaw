import { describe, expect, it } from "vitest";
import { buildConsultationRequest, buildConsultationResult } from "./consultation.js";

describe("collaboration consultation", () => {
  it("builds a bounded consultation request with only shared scopes", () => {
    const request = buildConsultationRequest({
      ownerAgentId: "ceo",
      targetAgentId: "ops",
      question: "What is the execution risk?",
      threadSummary: "Budget increase discussion",
      projectScope: "project:proj-a",
      roleScope: "role:ceo",
      privateScope: "private:UCEO1234",
    });

    expect(request).toEqual({
      ownerAgentId: "ceo",
      targetAgentId: "ops",
      question: "What is the execution risk?",
      threadSummary: "Budget increase discussion",
      sharedScopes: [
        { kind: "project", scope: "project:proj-a" },
        { kind: "role", scope: "role:ceo" },
      ],
    });
  });

  it("does not forward private scope into consultation payloads", () => {
    const request = buildConsultationRequest({
      ownerAgentId: "product",
      targetAgentId: "ops",
      question: "Can this ship this week?",
      privateScope: "private:UPM12345",
    });

    expect(request.sharedScopes).toEqual([]);
    expect(JSON.stringify(request)).not.toContain("private:UPM12345");
  });

  it("builds consultation results that return to the owner agent", () => {
    const request = buildConsultationRequest({
      ownerAgentId: "ceo",
      targetAgentId: "product",
      question: "What is the user impact?",
      projectScope: "project:proj-a",
    });

    expect(
      buildConsultationResult({
        request,
        answer: "User impact is high if we slip the launch.",
      }),
    ).toEqual({
      ownerAgentId: "ceo",
      targetAgentId: "product",
      answer: "User impact is high if we slip the launch.",
    });
  });
});
