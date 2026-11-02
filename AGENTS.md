# Supporter maintenance

Supporter is a Windows, keyboard-first assistant: Electron UI → NDJSON Python service → self-detecting CLI adapters. Read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for ownership and data flow, and [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for commands.

## Product invariants

- Ctrl+Space wakes beside the original input. Blur hides while preserving context and active generation. Esc closes that context. `/cancel` and busy Ctrl+C stop generation while preserving the conversation and draft.
- AI explanation and accepted replacement remain separate. Tab accepts only the selected candidate. Multiple command branches require a deliberate selection. Terminal insertion never sends Enter; multiline/unknown targets use full-text clipboard fallback.
- Explicit shell `/env` enables backtick completion. Public specs, user definitions and locally learned usage are separate. Never persist argument values, paths, credentials or conversations as learned habits.
- Backend plugins reload from the current machine. Removing a CLI/plugin removes availability; checking alone does not permanently switch a valid preference. Automatic refresh preserves drafts, candidates, generation and unsaved settings.
- `RESOURCE_ROOT` is immutable. Settings, logs, request files, editable plugins and COM code generation belong under `DATA_ROOT`. Installed users need no host Python/Node. Distributed defaults contain no developer account, proxy or habits.

## Work and verification

Keep production edits with the primary agent. When a change spans UI, backend/native or distribution, use available subagents for independent verification with disjoint test files; provide the actual result and distinguish fixtures, real runtime tests and skips. Do not use a subagent's predicted result as evidence.

Start with focused checks, then the relevant integration suite. Core: `python -m unittest discover -s tests -q`. UI: `powershell -NoProfile -ExecutionPolicy Bypass -File tests/run-frontend.ps1`; welcome: `tests/run-onboarding.ps1`. Distribution: `npm run dist:win` and `tests/packaged_smoke.py` against the built resources. See the development guide for exact options and other checks.

Use isolated data/profile/plugin directories for tests. Never type test commands into a user's terminal or modify their CLI login, global Codex settings, proxy or installed tools. Live account-backed benchmarks are opt-in and separate from unit/CI checks. Own fixture windows may be exercised after checking their HWND and foreground ownership; skip on focus mismatch.

Source and distribution use explicit allowlists. Do not commit `settings.json`, user completion JSON, `.runtime`, `.vendor`, caches, account files, downloaded runtimes or release binaries. Add new product modules/bundled plugins to `scripts/prepare-runtime.py` and update release tests. Treat backend detection/model metadata as executable boundaries, not trusted prompts.

## Delivery

Use [supporter-maintenance](.agents/skills/supporter-maintenance/SKILL.md) for implementation, [supporter-backend-plugin](.agents/skills/supporter-backend-plugin/SKILL.md) for adapters and [supporter-release](.agents/skills/supporter-release/SKILL.md) for distribution. Validate the kit with `python scripts/validate-agent-kit.py`.

Finish already-authorized work before asking for new decisions. Publishing/pushing requires the user's request; an explicit request already present in the session is sufficient and should not be requested again. Report what changed, validation and actual limitations; never claim a signed installer, Linux host integration, universal editor support or fixed model latency without evidence.
