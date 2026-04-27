import { describe, expect, it, vi } from "vitest";
import type { ConfigFileSnapshot } from "../config/types.js";
import { collaborationValidateCommand } from "./collaboration-validate.js";

const readConfigFileSnapshot = vi.fn<() => Promise<ConfigFileSnapshot>>();

vi.mock("../config/config.js", async () => {
  const actual = await vi.importActual<typeof import("../config/config.js")>("../config/config.js");
  return {
    ...actual,
    readConfigFileSnapshot: () => readConfigFileSnapshot(),
  };
});

function createRuntime() {
  const logs: string[] = [];
  const errors: string[] = [];
  return {
    logs,
    errors,
    runtime: {
      log: vi.fn((value: string) => logs.push(value)),
      error: vi.fn((value: string) => errors.push(value)),
      exit: vi.fn((code: number) => {
        throw new Error(`__exit__:${code}`);
      }),
    },
  };
}

function buildSnapshot(params: Partial<ConfigFileSnapshot>): ConfigFileSnapshot {
  return {
    path: "/tmp/openclaw.json",
    exists: true,
    raw: "{}",
    parsed: {},
    sourceConfig: {},
    resolved: {},
    valid: true,
    runtimeConfig: {},
    config: {},
    issues: [],
    warnings: [],
    legacyIssues: [],
    ...params,
  };
}

describe("collaborationValidateCommand", () => {
  it("prints JSON success for a valid collaboration config", async () => {
    readConfigFileSnapshot.mockResolvedValueOnce(
      buildSnapshot({
        config: {
          collaboration: {
            version: 1,
            identities: { users: {} },
            bots: {},
            roles: {},
            spaces: {},
          },
        },
      }),
    );
    const { logs, runtime } = createRuntime();

    await collaborationValidateCommand({ json: true }, runtime);

    expect(JSON.parse(logs[0] ?? "")).toEqual({
      valid: true,
      path: "/tmp/openclaw.json",
      hasCollaboration: true,
    });
  });

  it("reports missing collaboration config", async () => {
    readConfigFileSnapshot.mockResolvedValueOnce(buildSnapshot({ config: {} }));
    const { logs, runtime } = createRuntime();

    await expect(collaborationValidateCommand({ json: true }, runtime)).rejects.toThrow(
      "__exit__:1",
    );

    expect(JSON.parse(logs[0] ?? "")).toEqual({
      valid: false,
      path: "/tmp/openclaw.json",
      hasCollaboration: false,
      issues: [
        {
          path: "collaboration",
          message: "collaboration config missing",
        },
      ],
    });
  });

  it("forwards config validation issues", async () => {
    readConfigFileSnapshot.mockResolvedValueOnce(
      buildSnapshot({
        valid: false,
        issues: [
          {
            path: "collaboration.bots.product_bot.agentId",
            message: 'agent not found: "missing-agent"',
          },
        ],
      }),
    );
    const { logs, runtime } = createRuntime();

    await expect(collaborationValidateCommand({ json: true }, runtime)).rejects.toThrow(
      "__exit__:1",
    );

    expect(JSON.parse(logs[0] ?? "")).toEqual({
      valid: false,
      path: "/tmp/openclaw.json",
      hasCollaboration: false,
      issues: [
        {
          path: "collaboration.bots.product_bot.agentId",
          message: 'agent not found: "missing-agent"',
        },
      ],
    });
  });
});
