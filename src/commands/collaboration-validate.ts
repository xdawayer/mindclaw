import { CONFIG_PATH, readConfigFileSnapshot } from "../config/config.js";
import { formatConfigIssueLines, normalizeConfigIssues } from "../config/issue-format.js";
import type { ConfigValidationIssue } from "../config/types.js";
import { danger, success } from "../globals.js";
import type { RuntimeEnv } from "../runtime.js";
import { writeRuntimeJson } from "../runtime.js";
import { shortenHomePath } from "../utils.js";

function missingCollaborationIssue(): ConfigValidationIssue {
  return {
    path: "collaboration",
    message: "collaboration config missing",
  };
}

export async function collaborationValidateCommand(
  opts: { json?: boolean },
  runtime: RuntimeEnv,
): Promise<void> {
  let outputPath = CONFIG_PATH ?? "openclaw.json";

  try {
    const snapshot = await readConfigFileSnapshot();
    outputPath = snapshot.path;
    const shortPath = shortenHomePath(outputPath);

    if (!snapshot.exists) {
      if (opts.json) {
        writeRuntimeJson(runtime, { valid: false, path: outputPath, error: "file not found" }, 0);
      } else {
        runtime.error(danger(`Config file not found: ${shortPath}`));
      }
      runtime.exit(1);
      return;
    }

    const issues = !snapshot.valid
      ? normalizeConfigIssues(snapshot.issues)
      : snapshot.config.collaboration
        ? []
        : [missingCollaborationIssue()];

    if (issues.length > 0) {
      if (opts.json) {
        writeRuntimeJson(
          runtime,
          {
            valid: false,
            path: outputPath,
            hasCollaboration: Boolean(snapshot.config.collaboration),
            issues,
          },
          0,
        );
      } else {
        runtime.error(danger(`Collaboration config invalid at ${shortPath}:`));
        for (const line of formatConfigIssueLines(issues, danger("×"), { normalizeRoot: true })) {
          runtime.error(`  ${line}`);
        }
      }
      runtime.exit(1);
      return;
    }

    if (opts.json) {
      writeRuntimeJson(
        runtime,
        {
          valid: true,
          path: outputPath,
          hasCollaboration: true,
        },
        0,
      );
    } else {
      runtime.log(success(`Collaboration config valid: ${shortPath}`));
    }
  } catch (err) {
    if (opts.json) {
      writeRuntimeJson(runtime, { valid: false, path: outputPath, error: String(err) }, 0);
    } else {
      runtime.error(danger(`Collaboration validation error: ${String(err)}`));
    }
    runtime.exit(1);
  }
}
