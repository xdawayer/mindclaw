import { describe, expect, it } from "vitest";
import { applyHandoff, createHandoff } from "./handoff.js";

describe("collaboration handoff", () => {
  it("creates explicit handoff records", () => {
    expect(
      createHandoff({
        ownerAgentId: "ceo",
        nextAgentId: "ops",
        reason: "Ops should take over execution.",
        requestedBy: "UCEO1234",
      }),
    ).toEqual({
      ownerAgentId: "ceo",
      nextAgentId: "ops",
      reason: "Ops should take over execution.",
      requestedBy: "UCEO1234",
    });
  });

  it("changes owner only when the handoff matches the current owner", () => {
    const handoff = createHandoff({
      ownerAgentId: "ceo",
      nextAgentId: "ops",
      reason: "Ops should take over execution.",
    });

    expect(
      applyHandoff({
        currentOwnerAgentId: "ceo",
        handoff,
      }),
    ).toBe("ops");

    expect(
      applyHandoff({
        currentOwnerAgentId: "product",
        handoff,
      }),
    ).toBe("product");
  });
});
