import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const hasAnyAuthProfileStoreSourceMock = vi.fn(() => false);

vi.mock("../../agents/auth-profiles/source-check.js", () => ({
  hasAnyAuthProfileStoreSource: hasAnyAuthProfileStoreSourceMock,
}));

import type { CronJob } from "../types.js";
import {
  clearFastTestEnv,
  loadRunCronIsolatedAgentTurn,
  resolveSessionAuthProfileOverrideMock,
  resetRunCronIsolatedAgentTurnHarness,
  restoreFastTestEnv,
} from "./run.test-harness.js";

const runCronIsolatedAgentTurn = await loadRunCronIsolatedAgentTurn();

function makeParams(overrides?: Record<string, unknown>) {
  const job: CronJob = {
    id: "cron-auth-cold-path",
    name: "Auth Cold Path",
    enabled: true,
    createdAtMs: 0,
    updatedAtMs: 0,
    schedule: { kind: "cron", expr: "0 * * * *", tz: "UTC" },
    sessionTarget: "isolated",
    wakeMode: "next-heartbeat",
    payload: { kind: "agentTurn", message: "run task" },
    state: {},
  };
  return {
    cfg: {},
    deps: {} as never,
    job,
    message: "run task",
    sessionKey: "cron:auth-cold-path",
    ...overrides,
  };
}

describe("runCronIsolatedAgentTurn auth-profile cold path", () => {
  let previousFastTestEnv: string | undefined;

  beforeEach(() => {
    previousFastTestEnv = clearFastTestEnv();
    resetRunCronIsolatedAgentTurnHarness();
    hasAnyAuthProfileStoreSourceMock.mockReset();
    hasAnyAuthProfileStoreSourceMock.mockReturnValue(false);
  });

  afterEach(() => {
    restoreFastTestEnv(previousFastTestEnv);
  });

  it("skips auth-profile override resolution when no sources exist", async () => {
    const result = await runCronIsolatedAgentTurn(makeParams());

    expect(result.status).toBe("ok");
    expect(hasAnyAuthProfileStoreSourceMock).toHaveBeenCalledTimes(1);
    expect(resolveSessionAuthProfileOverrideMock).not.toHaveBeenCalled();
  });
});
