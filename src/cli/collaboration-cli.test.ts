import { Command } from "commander";
import { beforeEach, describe, expect, it, vi } from "vitest";

const collaborationValidateCommand = vi.fn(async () => {});
const collaborationExplainCommand = vi.fn(async () => {});
const collaborationAuditCommand = vi.fn(async () => {});

vi.mock("../commands/collaboration-validate.js", () => ({
  collaborationValidateCommand: (opts: unknown, runtime: unknown) =>
    collaborationValidateCommand(opts, runtime),
}));

vi.mock("../commands/collaboration-explain.js", () => ({
  collaborationExplainCommand: (opts: unknown, runtime: unknown) =>
    collaborationExplainCommand(opts, runtime),
}));

vi.mock("../commands/collaboration-audit.js", () => ({
  collaborationAuditCommand: (opts: unknown, runtime: unknown) =>
    collaborationAuditCommand(opts, runtime),
}));

const { registerCollaborationCli } = await import("./collaboration-cli.js");

describe("collaboration-cli", () => {
  const createProgram = () => {
    const program = new Command();
    program.exitOverride();
    registerCollaborationCli(program);
    return program;
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("dispatches collaboration validate", async () => {
    const program = createProgram();

    await program.parseAsync(["collaboration", "validate", "--json"], { from: "user" });

    expect(collaborationValidateCommand).toHaveBeenCalledWith(
      { json: true },
      expect.objectContaining({
        log: expect.any(Function),
        error: expect.any(Function),
        exit: expect.any(Function),
      }),
    );
  });

  it("dispatches collaboration explain", async () => {
    const program = createProgram();

    await program.parseAsync(
      ["collaboration", "explain", "--user", "U111PM001", "--channel", "C111PROJ01", "--json"],
      { from: "user" },
    );

    expect(collaborationExplainCommand).toHaveBeenCalledWith(
      {
        account: undefined,
        user: "U111PM001",
        channel: "C111PROJ01",
        thread: undefined,
        json: true,
      },
      expect.objectContaining({
        log: expect.any(Function),
        error: expect.any(Function),
        exit: expect.any(Function),
      }),
    );
  });

  it("dispatches collaboration audit", async () => {
    const program = createProgram();

    await program.parseAsync(
      [
        "collaboration",
        "audit",
        "--agent",
        "product",
        "--type",
        "route",
        "--correlation",
        "handoff-1",
        "--limit",
        "5",
        "--json",
      ],
      { from: "user" },
    );

    expect(collaborationAuditCommand).toHaveBeenCalledWith(
      {
        agent: "product",
        account: undefined,
        user: undefined,
        channel: undefined,
        thread: undefined,
        type: "route",
        correlation: "handoff-1",
        limit: 5,
        json: true,
      },
      expect.objectContaining({
        log: expect.any(Function),
        error: expect.any(Function),
        exit: expect.any(Function),
      }),
    );
  });

  it("accepts the handoff-run audit filter", async () => {
    const program = createProgram();

    await program.parseAsync(
      [
        "collaboration",
        "audit",
        "--agent",
        "ops",
        "--type",
        "handoff-run",
        "--correlation",
        "handoff-1",
      ],
      { from: "user" },
    );

    expect(collaborationAuditCommand).toHaveBeenCalledWith(
      {
        agent: "ops",
        account: undefined,
        user: undefined,
        channel: undefined,
        thread: undefined,
        type: "handoff-run",
        correlation: "handoff-1",
        limit: 20,
        json: false,
      },
      expect.objectContaining({
        log: expect.any(Function),
        error: expect.any(Function),
        exit: expect.any(Function),
      }),
    );
  });
});
