import type { OpenClawConfig } from "openclaw/plugin-sdk/config-runtime";
import { describe, expect, it } from "vitest";
import { isBotMessageBlockedByCollaboration } from "./collaboration.runtime.js";

function buildCfg(overrides?: Partial<NonNullable<OpenClawConfig["collaboration"]>>): OpenClawConfig {
  return {
    collaboration: {
      version: 1,
      mode: "enforced",
      identities: { users: {} },
      bots: {},
      roles: {},
      spaces: {
        project_main: {
          kind: "project",
          ownerRole: "product",
          slack: {
            channels: ["C123"],
          },
        },
      },
      ...overrides,
    },
  } as OpenClawConfig;
}

describe("isBotMessageBlockedByCollaboration", () => {
  it("does not block when the message is not bot-authored", () => {
    expect(
      isBotMessageBlockedByCollaboration({
        cfg: buildCfg(),
        channelId: "C123",
        isBotMessage: false,
      }),
    ).toBe(false);
  });

  it("does not block bot messages on unmanaged channels", () => {
    expect(
      isBotMessageBlockedByCollaboration({
        cfg: buildCfg(),
        channelId: "C999",
        isBotMessage: true,
      }),
    ).toBe(false);
  });

  it("blocks bot messages in spaces configured with allowBotMessages=none", () => {
    expect(
      isBotMessageBlockedByCollaboration({
        cfg: buildCfg({
          spaces: {
            project_main: {
              kind: "project",
              ownerRole: "product",
              slack: {
                channels: ["C123"],
                allowBotMessages: "none",
              },
            },
          },
        }),
        channelId: "C123",
        isBotMessage: true,
      }),
    ).toBe(true);
  });

  it("blocks bot messages on managed surfaces by default to prevent loops", () => {
    expect(
      isBotMessageBlockedByCollaboration({
        cfg: buildCfg(),
        channelId: "C123",
        isBotMessage: true,
      }),
    ).toBe(true);
  });

  it("allows bot messages when allowBotAuthoredReentry is opted in", () => {
    expect(
      isBotMessageBlockedByCollaboration({
        cfg: buildCfg({
          routing: {
            handoff: { allowBotAuthoredReentry: true },
          },
        }),
        channelId: "C123",
        isBotMessage: true,
      }),
    ).toBe(false);
  });

  it("still blocks when a space forces allowBotMessages=none even if reentry is on", () => {
    expect(
      isBotMessageBlockedByCollaboration({
        cfg: buildCfg({
          routing: {
            handoff: { allowBotAuthoredReentry: true },
          },
          spaces: {
            project_main: {
              kind: "project",
              ownerRole: "product",
              slack: {
                channels: ["C123"],
                allowBotMessages: "none",
              },
            },
          },
        }),
        channelId: "C123",
        isBotMessage: true,
      }),
    ).toBe(true);
  });

  it("does nothing when collaboration is not configured", () => {
    expect(
      isBotMessageBlockedByCollaboration({
        cfg: {} as OpenClawConfig,
        channelId: "C123",
        isBotMessage: true,
      }),
    ).toBe(false);
  });
});
