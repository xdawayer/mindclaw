import { describe, expect, it } from "vitest";
import {
  makeIsolatedAgentTurnJob,
  makeIsolatedAgentTurnParams,
  setupRunCronIsolatedAgentTurnSuite,
} from "./run.suite-helpers.js";
import {
  loadRunCronIsolatedAgentTurn,
  makeCronSession,
  resolveCronSessionMock,
  updateSessionStoreMock,
} from "./run.test-harness.js";

const runCronIsolatedAgentTurn = await loadRunCronIsolatedAgentTurn();

describe("runCronIsolatedAgentTurn — collaboration schedule metadata", () => {
  setupRunCronIsolatedAgentTurnSuite();

  it("persists collaboration scope metadata for collaboration cron jobs", async () => {
    const cronSession = makeCronSession();
    resolveCronSessionMock.mockReturnValue(cronSession);

    const result = await runCronIsolatedAgentTurn(
      makeIsolatedAgentTurnParams({
        job: makeIsolatedAgentTurnJob({
          id: "collab:ceo_daily_digest",
          collaboration: {
            source: "collaboration",
            sourceJobId: "ceo_daily_digest",
            ownerRole: "ceo",
            effectiveRole: "ceo",
            readableScopes: ["private", "role_shared"],
            publishableScopes: [],
            sourceSpaces: ["role_ceo"],
          },
        }),
      }),
    );

    expect(result.status).toBe("ok");
    expect(cronSession.sessionEntry.collaboration).toEqual({
      mode: "enforced",
      managedSurface: true,
      ownerRole: "ceo",
      effectiveRole: "ceo",
      readableScopes: ["private", "role_shared"],
      publishableScopes: [],
    });
    expect(updateSessionStoreMock).toHaveBeenCalled();
  });
});
