# Repository Guidelines

- Repo: https://github.com/openclaw/openclaw
- In chat replies, file references must be repo-root relative only (example: `src/telegram/index.ts:80`); never absolute paths or `~/...`.
- Do not edit files covered by security-focused `CODEOWNERS` rules unless a listed owner explicitly asked for the change or is already reviewing it with you. Treat those paths as restricted surfaces, not drive-by cleanup.

## Project Structure & Module Organization

- Source code: `src/` (CLI wiring in `src/cli`, commands in `src/commands`, web provider in `src/provider-web.ts`, infra in `src/infra`, media pipeline in `src/media`).
- Tests: colocated `*.test.ts`.
- Docs: `docs/` (images, queue, Pi config). Built output lives in `dist/`.
- Nomenclature: use "plugin" / "plugins" in docs, UI, changelogs, and contributor guidance. The bundled workspace plugin tree remains the internal package layout to avoid repo-wide churn from a rename.
- Bundled plugin naming: for repo-owned workspace plugins, keep the canonical plugin id aligned across `openclaw.plugin.json:id`, the default workspace folder name, and package names anchored to the same id (`@openclaw/<id>` or approved suffix forms like `-provider`, `-plugin`, `-speech`, `-sandbox`, `-media-understanding`). Keep `openclaw.install.npmSpec` equal to the package name and `openclaw.channel.id` equal to the plugin id when present. Exceptions must be explicit and covered by the repo invariant test.
- Plugins: live in the bundled workspace plugin tree (workspace packages). Keep plugin-only deps in the extension `package.json`; do not add them to the root `package.json` unless core uses them.
- Plugins: install runs `npm install --omit=dev` in plugin dir; runtime deps must live in `dependencies`. Avoid `workspace:*` in `dependencies` (npm install breaks); put `openclaw` in `devDependencies` or `peerDependencies` instead (runtime resolves `openclaw/plugin-sdk` via jiti alias).
- Import boundaries: extension production code should treat `openclaw/plugin-sdk/*` plus local `api.ts` / `runtime-api.ts` barrels as the public surface. Do not import core `src/**`, `src/plugin-sdk-internal/**`, or another extension's `src/**` directly.
- Installers served from `https://openclaw.ai/*`: live in the sibling repo `../openclaw.ai` (`public/install.sh`, `public/install-cli.sh`, `public/install.ps1`).
- Messaging channels: always consider **all** built-in + extension channels when refactoring shared logic (routing, allowlists, pairing, command gating, onboarding, docs).
  - Core channel docs: `docs/channels/`
  - Core channel code: `src/telegram`, `src/discord`, `src/slack`, `src/signal`, `src/imessage`, `src/web` (WhatsApp web), `src/channels`, `src/routing`
  - Bundled plugin channels: the workspace plugin tree (for example Matrix, Zalo, ZaloUser, Voice Call)
- When adding channels/plugins/apps/docs, update `.github/labeler.yml` and create matching GitHub labels (use existing channel/plugin label colors).

## Architecture Boundaries

- Repo map:
  - bundled workspace plugin tree = bundled plugins + third-party plugin example surface
  - `src/plugin-sdk/*` = public plugin contract for extensions
  - `src/channels/*` = core channel implementation (behind plugin boundary)
  - `src/plugins/*` = plugin discovery, manifest, loader, registry, contract enforcement
  - `src/gateway/protocol/*` = typed Gateway control-plane and node wire protocol
- **Detailed boundary rules live in local `AGENTS.md` guides** — read them when working in that area:
  - `extensions/AGENTS.md`, `src/plugin-sdk/AGENTS.md`, `src/channels/AGENTS.md`, `src/plugins/AGENTS.md`, `src/gateway/protocol/AGENTS.md`, `test/helpers/AGENTS.md`
- Workflow hygiene: read only guides relevant to the files/boundary you are touching. Do not grep every path in this file before starting. Full broken-link sweeps only for docs/repo-instruction maintenance tasks.
- Core principles (details in boundary guides above):
  - Core must stay extension-agnostic; extensions cross into core only through `openclaw/plugin-sdk/*`, manifest metadata, and documented runtime helpers.
  - Do not hardcode extension/provider/channel id lists in core; use manifest/capability/registry patterns.
  - Extension-owned behavior (legacy repairs, auth detection, provider defaults) belongs in the owning extension, not core.
  - New plugin seams must be documented, backwards-compatible, versioned contracts (third-party plugins exist).
  - `src/channels/**` is core implementation; plugin authors use Plugin SDK seams, not channel internals.
  - Protocol changes are contract changes — prefer additive evolution with explicit versioning.
  - Keep public config surfaces (types, zod/schema, help/labels, baselines, gateway payloads) aligned; retired keys go through migration/doctor seams only.
  - Extension test coverage belongs under the owning plugin package; core tests assert generic contracts via `src/plugin-sdk/<id>.ts` facades or `api.ts`.
- Plugin architecture direction: manifest-first control plane (metadata-driven discovery/validation/enablement). Runtime execution via narrow targeted loaders, not broad registry materialization. Host loads plugins; plugins don't load host internals. Treat broad runtime registries as transitional.

## Scoped Workflow Guides

- `docs/AGENTS.md` owns Mintlify docs, docs links, and docs i18n rules.
- `ui/AGENTS.md` owns Control UI i18n and generated locale rules.
- `scripts/AGENTS.md` owns script-runner, local-check lock, and test/lint wrapper rules.

## exe.dev VM ops (general)

- Access: stable path is `ssh exe.dev` then `ssh vm-name` (assume SSH key already set).
- SSH flaky: use exe.dev web terminal or Shelley (web agent); keep a tmux session for long ops.
- Update: `sudo npm i -g openclaw@latest` (global install needs root on `/usr/lib/node_modules`).
- Config: use `openclaw config set ...`; ensure `gateway.mode=local` is set.
- Discord: store raw token only (no `DISCORD_BOT_TOKEN=` prefix).
- Restart: stop old gateway and run:
  `pkill -9 -f openclaw-gateway || true; nohup openclaw gateway run --bind loopback --port 18789 --force > /tmp/openclaw-gateway.log 2>&1 &`
- Verify: `openclaw channels status --probe`, `ss -ltnp | rg 18789`, `tail -n 120 /tmp/openclaw-gateway.log`.

## Build, Test, and Development Commands

- Runtime baseline: Node **22+** (keep Node + Bun paths working).
- Install deps: `pnpm install`
- If deps are missing (for example `node_modules` missing, `vitest not found`, or `command not found`), run the repo’s package-manager install command (prefer lockfile/README-defined PM), then rerun the exact requested command once. Apply this to test/build/lint/typecheck/dev commands; if retry still fails, report the command and first actionable error.
- Pre-commit hooks: `prek install`. The hook runs the repo verification flow, including `pnpm check`.
- `FAST_COMMIT=1` skips the repo-wide `pnpm format` and `pnpm check` inside the pre-commit hook only. Use it when you intentionally want a faster commit path and are running equivalent targeted verification manually. It does not change CI and does not change what `pnpm check` itself does.
- Also supported: `bun install` (keep `pnpm-lock.yaml` + Bun patching in sync when touching deps/patches).
- Prefer Bun for TypeScript execution (scripts, dev, tests): `bun <file.ts>` / `bunx <tool>`.
- Run CLI in dev: `pnpm openclaw ...` (bun) or `pnpm dev`.
- Node remains supported for running built output (`dist/*`) and production installs.
- Mac packaging (dev): `scripts/package-mac-app.sh` defaults to current arch.
- Type-check/build: `pnpm build`
- TypeScript checks: `pnpm tsgo`
- Lint/format: `pnpm check`
- Local agent/dev shells default to host-aware `OPENCLAW_LOCAL_CHECK=1` behavior for `pnpm tsgo` and `pnpm lint`; set `OPENCLAW_LOCAL_CHECK_MODE=throttled` to force the lower-memory profile, `OPENCLAW_LOCAL_CHECK_MODE=full` to keep lock-only behavior, or `OPENCLAW_LOCAL_CHECK=0` in CI/shared runs.
- Format check: `pnpm format` (oxfmt --check)
- Format fix: `pnpm format:fix` (oxfmt --write)
- Gates: local dev = `pnpm check` (+ scoped tests); landing = `pnpm check` + `pnpm test` (+ `pnpm build` if touching build/packaging/module boundaries); CI = workflow-defined (`check`, `check-additional`, `build-smoke`, etc.).
- `check-additional` enforces architecture/boundary policy guards kept out of the default local loop.
- Pre-commit hook runs `pnpm format` then `pnpm check`. `FAST_COMMIT=1 git commit ...` skips both in the hook.
- Tests: `pnpm test` (vitest); coverage: `pnpm test:coverage`
- Generated baseline drift detection uses SHA-256 hash files under `docs/.generated/` (`.sha256` files tracked in git; full JSON baselines are gitignored, generated locally for inspection).
- Config schema drift uses `pnpm config:docs:gen` / `pnpm config:docs:check`.
- Plugin SDK API drift uses `pnpm plugin-sdk:api:gen` / `pnpm plugin-sdk:api:check`.
- If you change config schema/help or the public Plugin SDK surface, run the matching gen command and commit the updated `.sha256` hash file. Keep the two drift-check flows adjacent in scripts/workflows/docs guidance rather than inventing a third pattern.
- When `pnpm tsgo` fails, triage by coherent surface instead of by raw error count: rerun the gate, group failures by package/module/type contract, open the source-of-truth type or export file first, fix the root mismatch, then rerun `pnpm tsgo` before widening into downstream consumers. Check `origin/main` before doing broad cleanup because some apparent type debt is already fixed upstream.
- For narrowly scoped changes, prefer narrowly scoped tests that directly validate the touched behavior. If no meaningful scoped test exists, say so explicitly and use the next most direct validation available.
- Verification modes: Default (stable `main`) — count pre-commit coverage, avoid redundant reruns, keep CI green. Fast-commit (`FAST_COMMIT=1`) — shorter loops, `--no-verify` OK for intermediate commits if equivalent checks ran locally.
- Landing bar: `pnpm check` + `pnpm test` near final push. Hard gate: `pnpm build` MUST pass if change can affect build output, packaging, or module boundaries.
- Do not land with failing checks caused by or plausibly related to the touched surface. For narrowly scoped changes with pre-existing unrelated failures on `origin/main`, report scoped tests and ask before broadening.

## Prompt Cache Stability

- Treat prompt-cache stability as correctness/perf-critical, not cosmetic.
- Any code that assembles model or tool payloads from maps, sets, registries, plugin lists, MCP catalogs, filesystem reads, or network results must make ordering deterministic before building the request.
- Do not rewrite older transcript/history bytes on every turn unless you intentionally want to invalidate the cached prefix. Legacy cleanup, pruning, normalization, and migration logic should preserve recent prompt bytes when possible.
- If truncation or compaction is required, prefer mutating newest or tail content first so the cached prefix stays byte-identical for as long as possible.
- For cache-sensitive changes, require a regression test that proves turn-to-turn prefix stability or deterministic request assembly; helper-local tests alone are not enough.

## Coding Style & Naming Conventions

- Language: TypeScript (ESM). Prefer strict typing; avoid `any`.
- Formatting/linting via Oxlint and Oxfmt.
- Never add `@ts-nocheck` and do not add inline lint suppressions by default. Fix root causes first; only keep a suppression when the code is intentionally correct, the rule cannot express that safely, and the comment explains why.
- Do not disable `no-explicit-any`; prefer real types, `unknown`, or a narrow adapter/helper instead. Update Oxlint/Oxfmt config only when required.
- Prefer `zod` or existing schema helpers at external boundaries such as config, webhook payloads, CLI/JSON output, persisted JSON, and third-party API responses.
- Prefer discriminated unions when parameter shape changes runtime behavior.
- Prefer `Result<T, E>`-style outcomes and closed error-code unions for recoverable runtime decisions.
- Keep human-readable strings for logs, CLI output, and UI; do not use freeform strings as the source of truth for internal branching.
- Avoid `?? 0`, empty-string, empty-object, or magic-string sentinels when they can change runtime meaning silently.
- If introducing a new optional field or nullable semantic in core logic, prefer an explicit union or dedicated type when the value changes behavior.
- New runtime control-flow code should not branch on `error: string` or `reason: string` when a closed code union would be reasonable.
- Dynamic import guardrail: do not mix `await import("x")` and static `import ... from "x"` for the same module in production code paths. If you need lazy loading, create a dedicated `*.runtime.ts` boundary (that re-exports from `x`) and dynamically import that boundary from lazy callers only.
- Dynamic import verification: after refactors that touch lazy-loading/module boundaries, run `pnpm build` and check for `[INEFFECTIVE_DYNAMIC_IMPORT]` warnings before submitting.
- Circular dependencies: keep both `pnpm check:import-cycles` and `pnpm check:madge-import-cycles` green; do not reintroduce runtime import cycles or madge-detected import loops.
- Extension SDK self-import guardrail: inside an extension package, do not import that same extension via `openclaw/plugin-sdk/<extension>` from production files. Route internal imports through a local barrel such as `./api.ts` or `./runtime-api.ts`, and keep the `plugin-sdk/<extension>` path as the external contract only.
- Extension package boundary guardrail: inside a bundled plugin package, do not use relative imports/exports that resolve outside that same package root. If shared code belongs in the plugin SDK, import `openclaw/plugin-sdk/<subpath>` instead of reaching into `src/plugin-sdk/**` or other repo paths via `../`.
- Extension API surface rule: `openclaw/plugin-sdk/<subpath>` is the only public cross-package contract for extension-facing SDK code. If an extension needs a new seam, add a public subpath first; do not reach into `src/plugin-sdk/**` by relative path.
- Never share class behavior via prototype mutation (`applyPrototypeMixins`, `Object.defineProperty` on `.prototype`, or exporting `Class.prototype` for merges). Use explicit inheritance/composition (`A extends B extends C`) or helper composition so TypeScript can typecheck.
- If this pattern is needed, stop and get explicit approval before shipping; default behavior is to split/refactor into an explicit class hierarchy and keep members strongly typed.
- In tests, prefer per-instance stubs over prototype mutation (`SomeClass.prototype.method = ...`) unless a test explicitly documents why prototype-level patching is required.
- Add brief code comments for tricky or non-obvious logic.
- Keep files concise; extract helpers instead of “V2” copies. Use existing patterns for CLI options and dependency injection via `createDefaultDeps`.
- Aim to keep files under ~700 LOC; guideline only (not a hard guardrail). Split/refactor when it improves clarity or testability.
- Naming: use **OpenClaw** for product/app/docs headings; use `openclaw` for CLI command, package/binary, paths, and config keys.
- Written English: use American spelling and grammar in code, comments, docs, and UI strings (e.g. "color" not "colour", "behavior" not "behaviour", "analyze" not "analyse").

## Release / Advisory Workflows

- Use `$openclaw-release-maintainer` at `.agents/skills/openclaw-release-maintainer/SKILL.md` for release naming, version coordination, release auth, and changelog-backed release-note workflows.
- Use `$openclaw-ghsa-maintainer` at `.agents/skills/openclaw-ghsa-maintainer/SKILL.md` for GHSA advisory inspection, patch/publish flow, private-fork checks, and GHSA API validation.
- Release and publish remain explicit-approval actions even when using the skill.

## Testing Guidelines

- Framework: Vitest with V8 coverage thresholds (70% lines/branches/functions/statements).
- Naming: match source names with `*.test.ts`; e2e in `*.e2e.test.ts`.
- When tests need example Anthropic/OpenAI model constants, prefer `sonnet-4.6` and `gpt-5.4`; update older Anthropic/GPT examples when you touch those tests.
- Run `pnpm test` (or `pnpm test:coverage`) before pushing when you touch logic.
- Write tests to clean up timers, env, globals, mocks, sockets, temp dirs, and module state so `--isolate=false` stays green.
- Test performance guardrails (all apply to keep `--isolate=false` fast):
  - Prefer static/`beforeAll` imports over `vi.resetModules()` + `await import(...)` per test. Reset mocks/state directly, not the module graph.
  - Use thin local seams (`./api.ts`, `*.runtime.ts`) over broad `openclaw/plugin-sdk/*` barrel imports in extensions and hot tests. Keep expensive runtime work (snapshotting, migration, bootstrap) behind `*.runtime.ts` boundaries.
  - Prefer explicit mock factories over `importOriginal()` for broad modules. Use existing `deps`/callback injection seams before adding module-level mocks.
  - Prefer narrow SDK subpaths (`models-provider-runtime`, `skill-commands-runtime`) over older broad barrels.
  - Treat import-dominated test time as a boundary bug — refactor the import surface before adding more cases.
- Agents MUST NOT modify baseline, inventory, ignore, snapshot, or expected-failure files to silence failing checks without explicit approval in this chat.
- For targeted/local debugging, use the native root-project entrypoint: `pnpm test <path-or-filter> [vitest args...]` (for example `pnpm test src/commands/onboard-search.test.ts -t "shows registered plugin providers"`); do not default to raw `pnpm vitest run ...` because it bypasses the repo's default config/profile/pool routing.
- Do not set test workers above 16; tried already.
- Vitest now defaults to native root-project `threads`, with hard `forks` exceptions for `gateway`, `agents`, and `commands`. Keep new pool changes explicit and justified; use `OPENCLAW_VITEST_POOL=forks` for full local fork debugging.
- If local Vitest runs cause memory pressure, the default worker budget now derives from host capabilities (CPU, memory band, current load). For a conservative explicit override during land/gate runs, use `OPENCLAW_VITEST_MAX_WORKERS=1 pnpm test`.
- Live tests (real keys): `OPENCLAW_LIVE_TEST=1 pnpm test:live` (OpenClaw-only) or `LIVE=1 pnpm test:live` (includes provider live tests). Docker: `pnpm test:docker:live-models`, `pnpm test:docker:live-gateway`. Onboarding Docker E2E: `pnpm test:docker:onboard`.
- `pnpm test:live` defaults quiet now. Keep `[live]` progress; suppress profile/gateway chatter. Full logs: `OPENCLAW_LIVE_TEST_QUIET=0 pnpm test:live`.
- Full kit + what’s covered: `docs/help/testing.md`.
- Changelog: user-facing changes only; no internal/meta notes (version alignment, appcast reminders, release process).
- Changelog placement: in the active version block, append new entries to the end of the target section (`### Changes` or `### Fixes`); do not insert new entries at the top of a section.
- Changelog attribution: use at most one contributor mention per line; prefer `Thanks @author` and do not also add `by @author` on the same entry.
- Pure test additions/fixes generally do **not** need a changelog entry unless they alter user-facing behavior or the user asks for one.
- Mobile: before using a simulator, check for connected real devices (iOS + Android) and prefer them when available.

## Commit & Pull Request Guidelines

- Use `$openclaw-pr-maintainer` at `.agents/skills/openclaw-pr-maintainer/SKILL.md` for maintainer PR triage, review, close, search, and landing workflows.
- This includes auto-close labels, bug-fix evidence gates, GitHub comment/search footguns, and maintainer PR decision flow.
- For the repo's end-to-end maintainer PR workflow, use `$openclaw-pr-maintainer` at `.agents/skills/openclaw-pr-maintainer/SKILL.md`.

- `/landpr` lives in the global Codex prompts (`~/.codex/prompts/landpr.md`); when landing or merging any PR, always follow that `/landpr` process.
- Create commits with `scripts/committer "<msg>" <file...>`; avoid manual `git add`/`git commit` so staging stays scoped.
- Follow concise, action-oriented commit messages (e.g., `CLI: add verbose flag to send`).
- Group related changes; avoid bundling unrelated refactors.
- PR submission template (canonical): `.github/pull_request_template.md`
- Issue submission templates (canonical): `.github/ISSUE_TEMPLATE/`

## Git Notes

- If `git branch -d/-D <branch>` is policy-blocked, delete the local ref directly: `git update-ref -d refs/heads/<branch>`.
- Agents MUST NOT create or push merge commits on `main`. If `main` has advanced, rebase local commits onto the latest `origin/main` before pushing.
- Bulk PR close/reopen safety: if a close action would affect more than 5 PRs, first ask for explicit user confirmation with the exact PR count and target scope/query.

## Security & Configuration Tips

- Web provider stores creds at `~/.openclaw/credentials/`; rerun `openclaw login` if logged out.
- Pi sessions live under `~/.openclaw/sessions/` by default; the base directory is not configurable.
- Environment variables: see `~/.profile`.
- Never commit or publish real phone numbers, videos, or live configuration values. Use obviously fake placeholders in docs, tests, and examples.
- Release flow: use the private [maintainer release docs](https://github.com/openclaw/maintainers/blob/main/release/README.md) for the actual runbook, `docs/reference/RELEASING.md` for the public release policy, and `$openclaw-release-maintainer` for the maintainership workflow.

## Local Runtime / Platform Notes

- Vocabulary: "makeup" = "mac app".
- Rebrand/migration issues or legacy config/service warnings: run `openclaw doctor` (see `docs/gateway/doctor.md`).
- Use `$openclaw-parallels-smoke` at `.agents/skills/openclaw-parallels-smoke/SKILL.md` for Parallels smoke, rerun, upgrade, debug, and result-interpretation workflows across macOS, Windows, and Linux guests.
- For the macOS Discord roundtrip deep dive, use the narrower `.agents/skills/parallels-discord-roundtrip/SKILL.md` companion skill.
- Never edit `node_modules` (global/Homebrew/npm/git installs too). Updates overwrite. Skill notes go in `tools.md` or `AGENTS.md`.
- If you need local-only `.agents` ignores, use `.git/info/exclude` instead of repo `.gitignore`.
- When adding a new `AGENTS.md` anywhere in the repo, also add a `CLAUDE.md` symlink pointing to it (example: `ln -s AGENTS.md CLAUDE.md`).
- Signal: "update fly" => `fly ssh console -a flawd-bot -C "bash -lc 'cd /data/clawd/openclaw && git pull --rebase origin main'"` then `fly machines restart e825232f34d058 -a flawd-bot`.
- CLI progress: use `src/cli/progress.ts` (`osc-progress` + `@clack/prompts` spinner); don’t hand-roll spinners/bars.
- Status output: keep tables + ANSI-safe wrapping (`src/terminal/table.ts`); `status --all` = read-only/pasteable, `status --deep` = probes.
- Gateway currently runs only as the menubar app; there is no separate LaunchAgent/helper label installed. Restart via the OpenClaw Mac app or `scripts/restart-mac.sh`; to verify/kill use `launchctl print gui/$UID | grep openclaw` rather than assuming a fixed label. **When debugging on macOS, start/stop the gateway via the app, not ad-hoc tmux sessions; kill any temporary tunnels before handoff.**
- macOS logs: use `./scripts/clawlog.sh` to query unified logs for the OpenClaw subsystem; it supports follow/tail/category filters and expects passwordless sudo for `/usr/bin/log`.
- If shared guardrails are available locally, review them; otherwise follow this repo's guidance.
- SwiftUI state management (iOS/macOS): prefer the `Observation` framework (`@Observable`, `@Bindable`) over `ObservableObject`/`@StateObject`; don’t introduce new `ObservableObject` unless required for compatibility, and migrate existing usages when touching related code.
- Connection providers: when adding a new connection, update every UI surface and docs (macOS app, web UI, mobile if applicable, onboarding/overview docs) and add matching status + configuration forms so provider lists and settings stay in sync.
- Version locations: `package.json`, `apps/android/app/build.gradle.kts`, `apps/ios/Sources/Info.plist` + `apps/ios/Tests/Info.plist`, `apps/macos/Sources/OpenClaw/Resources/Info.plist`, `docs/install/updating.md`, Peekaboo Xcode Info.plists. "Bump everywhere" = all except `appcast.xml` (appcast only for macOS Sparkle releases).
- **Restart apps:** “restart iOS/Android apps” means rebuild (recompile/install) and relaunch, not just kill/launch.
- **Device checks:** before testing, verify connected real devices (iOS/Android) before reaching for simulators/emulators.
- Mobile pairing: `ws://` OK for private LAN (RFC 1918, link-local, `.local`, loopback); `wss://` required for Tailscale/public endpoints. LAN-only `ws://` vuln reports are out of scope.
- iOS Team ID lookup: `security find-identity -p codesigning -v` → use Apple Development (…) TEAMID. Fallback: `defaults read com.apple.dt.Xcode IDEProvisioningTeamIdentifiers`.
- A2UI bundle hash: `src/canvas-host/a2ui/.bundle.hash` is auto-generated; ignore unexpected changes, and only regenerate via `pnpm canvas:a2ui:bundle` (or `scripts/bundle-a2ui.sh`) when needed. Commit the hash as a separate commit.
- Release signing/notary credentials are managed outside the repo; maintainers keep that setup in the private [maintainer release docs](https://github.com/openclaw/maintainers/tree/main/release).
- Lobster palette: use the shared CLI palette in `src/terminal/palette.ts` (no hardcoded colors); apply palette to onboarding/config prompts and other TTY UI output as needed.
- When asked to open a “session” file, open the Pi session logs under `~/.openclaw/agents/<agentId>/sessions/*.jsonl` (use the `agent=<id>` value in the Runtime line of the system prompt; newest unless a specific ID is given), not the default `sessions.json`. If logs are needed from another machine, SSH via Tailscale and read the same path there.
- Do not rebuild the macOS app over SSH; rebuilds must be run directly on the Mac.
- Voice wake: command template = `openclaw-mac agent --message "${text}" --thinking low` (no extra quotes — `VoiceWakeForwarder` shell-escapes). Ensure launch agent PATH includes pnpm bin (`$HOME/Library/pnpm`).

## Collaboration / Safety Notes

- When working on a GitHub Issue or PR, print the full URL at the end of the task.
- When answering questions, respond with high-confidence answers only: verify in code; do not guess.
- Carbon version edits are owner-only: do not change `@buape/carbon` version pins unless you are Shadow (@thewilloftheshadow) as verified by gh.
- Any dependency with `pnpm.patchedDependencies` must use an exact version (no `^`/`~`).
- Patching dependencies (pnpm patches, overrides, or vendored changes) requires explicit approval; do not do this by default.
- **Multi-agent safety:** No `git stash`, branch switches, or worktree changes unless explicitly requested. Scope commits to your changes only ("commit all" = grouped chunks). Use `git pull --rebase` (no `--autostash`) when pushing. Ignore unrecognized files — focus on your changes. Multiple agents OK if each has its own session.
- Lint/format churn:
  - If staged+unstaged diffs are formatting-only, auto-resolve without asking.
  - If commit/push already requested, auto-stage and include formatting-only follow-ups in the same commit (or a tiny follow-up commit if needed), no extra confirmation.
  - Only ask when changes are semantic (logic/data/behavior).
- **Multi-agent safety:** focus reports on your edits; avoid guard-rail disclaimers unless truly blocked; when multiple agents touch the same file, continue if safe; end with a brief “other files present” note only if relevant.
- Bug investigations: read source code of relevant npm dependencies and all related local code before concluding; aim for high-confidence root cause.
- Code style: add brief comments for tricky logic; keep files under ~700 LOC when feasible (split/refactor as needed).
- Tool schema guardrails (google-antigravity): avoid `Type.Union` in tool input schemas; no `anyOf`/`oneOf`/`allOf`. Use `stringEnum`/`optionalStringEnum` (Type.Unsafe enum) for string lists, and `Type.Optional(...)` instead of `... | null`. Keep top-level tool schema as `type: "object"` with `properties`.
- Tool schema guardrails: avoid raw `format` property names in tool schemas; some validators treat `format` as a reserved keyword and reject the schema.
- Never send streaming/partial replies to external messaging surfaces (WhatsApp, Telegram); only final replies should be delivered there. Streaming/tool events may still go to internal UIs/control channel.
- For manual `openclaw message send` messages that include `!`, use the heredoc pattern noted below to avoid the Bash tool’s escaping.
- Release guardrails: do not change version numbers without operator’s explicit consent; always ask permission before running any npm publish/release step.
- Beta release guardrail: when using a beta Git tag (for example `vYYYY.M.D-beta.N`), publish npm with a matching beta version suffix (for example `YYYY.M.D-beta.N`) rather than a plain version on `--tag beta`; otherwise the plain version name gets consumed/blocked.

## Diagnostic Accuracy Rules

When performing system diagnostics (cron status, service health, configuration checks):

- **Read the actual data source, not summaries.** For cron status, read `~/.openclaw/cron/jobs.json` directly and count `enabled: true` vs `enabled: false` fields. Do not infer counts from partial output or tool error messages.
- **Report exact numbers with evidence.** State "N of M jobs are enabled" with the specific job names, not "all jobs are disabled" without verifying each one.
- **Distinguish between disabled and errored.** A cron job with `enabled: true` that has `status: "error"` in its last run is a _failing job_, not a _disabled job_. These are different problems with different fixes.
- **Never say "all" without verifying every item.** If you checked 2 jobs and both are disabled, say "2 checked jobs are disabled" not "all jobs are disabled".
- **Include the verification command in your response.** When reporting system state, show the exact command or file you read so the user can verify independently (e.g., "Checked `~/.openclaw/cron/jobs.json`: 21 enabled, 6 disabled").
- **Cross-check when data sources conflict.** If `cron list` CLI output differs from `jobs.json` file content, report both and flag the discrepancy rather than picking one.

## Skill routing

When the user's request matches an available skill, ALWAYS invoke it using the Skill
tool as your FIRST action. Do NOT answer directly, do NOT use other tools first.
The skill has specialized workflows that produce better results than ad-hoc answers.

Key routing rules:

- Product ideas, "is this worth building", brainstorming → invoke yc-office-hours
- Bugs, errors, "why is this broken", 500 errors → invoke yc-investigate
- Ship, deploy, push, create PR → invoke yc-ship
- QA, test the site, find bugs → invoke yc-qa
- Code review, check my diff → invoke yc-review
- Update docs after shipping → invoke yc-document-release
- Weekly retro → invoke yc-retro
- Design system, brand → invoke yc-design-consultation
- Visual audit, design polish → invoke yc-design-review
- Architecture review → invoke yc-plan-eng-review
- Save progress, checkpoint, resume → invoke yc-checkpoint
- Code quality, health check → invoke yc-health
