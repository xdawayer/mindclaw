import { describe, expect, it, vi } from "vitest";
import type { ConfigFileSnapshot } from "../config/types.js";
import type { RuntimeEnv } from "../runtime.js";
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
  const runtime: RuntimeEnv = {
    log: vi.fn((...args: unknown[]) => {
      logs.push(args.map((v) => String(v)).join(" "));
    }),
    error: vi.fn((...args: unknown[]) => {
      errors.push(args.map((v) => String(v)).join(" "));
    }),
    exit: vi.fn((code: number) => {
      throw new Error(`__exit__:${code}`);
    }) as unknown as RuntimeEnv["exit"],
  };
  return { logs, errors, runtime };
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
