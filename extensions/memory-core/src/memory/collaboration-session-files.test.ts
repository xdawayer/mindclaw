import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import type { OpenClawConfig } from "openclaw/plugin-sdk/memory-core-host-engine-foundation";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { listSessionFilesForCollaborationScope } from "./collaboration-session-files.js";

const cfg: OpenClawConfig = {
  agents: {
    list: [
      { id: "product", default: true },
      { id: "ops" },
      { id: "ceo" },
    ],
  },
  collaboration: {
    spaces: {
      projects: {
        "proj-a": {
          channelId: "CPROJ1234",
          defaultAgent: "product",
          defaultDmRecipient: "UPM12345",
          roleDmRecipients: {
            ops: "UOPS1234",
            ceo: "UCEO1234",
          },
        },
      },
      roles: {
        ops: {
          channelId: "COPS12345",
          agentId: "ops",
        },
        ceo: {
          channelId: "CCEO12345",
          agentId: "ceo",
        },
      },
    },
  },
};

let tmpDir = "";
let originalStateDir: string | undefined;

async function writeAgentSession(params: {
  agentId: string;
  sessionKey: string;
  sessionId: string;
}) {
  const sessionsDir = path.join(tmpDir, "agents", params.agentId, "sessions");
  await fs.mkdir(sessionsDir, { recursive: true });
  await fs.writeFile(
    path.join(sessionsDir, "sessions.json"),
    JSON.stringify(
      {
        [params.sessionKey]: {
          sessionId: params.sessionId,
          updatedAt: Date.now(),
        },
      },
      null,
      2,
    ),
    "utf8",
  );
  await fs.writeFile(path.join(sessionsDir, `${params.sessionId}.jsonl`), "", "utf8");
}

describe("collaboration session file listing", () => {
  beforeEach(async () => {
    tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), "openclaw-collab-sessions-"));
    originalStateDir = process.env.OPENCLAW_STATE_DIR;
    process.env.OPENCLAW_STATE_DIR = tmpDir;
  });

  afterEach(async () => {
    if (originalStateDir === undefined) {
      delete process.env.OPENCLAW_STATE_DIR;
    } else {
      process.env.OPENCLAW_STATE_DIR = originalStateDir;
    }
    await fs.rm(tmpDir, { recursive: true, force: true });
  });

  it("collects project-scoped transcripts across collaboration participant agents", async () => {
    await writeAgentSession({
      agentId: "product",
      sessionKey: "agent:product:slack:channel:CPROJ1234:thread:1710000000.000100",
      sessionId: "product-thread",
    });
    await writeAgentSession({
      agentId: "ops",
      sessionKey: "agent:ops:slack:channel:CPROJ1234:thread:1710000000.000100",
      sessionId: "ops-thread",
    });
    await writeAgentSession({
      agentId: "ceo",
      sessionKey: "agent:ceo:slack:channel:CCEO12345",
      sessionId: "ceo-role-only",
    });

    const files = await listSessionFilesForCollaborationScope({
      cfg,
      collaborationScope: {
        kind: "project",
        scope: "project:proj-a",
      },
      candidateAgentIds: ["product", "ops", "ceo"],
    });

    expect(files.map((filePath) => path.basename(filePath)).toSorted()).toEqual(
      ["ops-thread.jsonl", "product-thread.jsonl"],
    );
  });
});
