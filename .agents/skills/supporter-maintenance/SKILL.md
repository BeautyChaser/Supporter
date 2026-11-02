---
name: supporter-maintenance
description: Implement and verify changes to Supporter UI, input behavior, service or packaging while preserving keyboard workflows and per-user state.
---

Read [AGENTS.md](../../../AGENTS.md) and the relevant boundary in [architecture](../../../docs/ARCHITECTURE.md). Reproduce the observable failure in an owned fixture or isolated test before choosing a fix.

For UI changes, preserve the original source target while the helper owns focus. Late generation/capture events must remain associated with their request IDs. A background catalog update must not reset draft state or change a `checking` preference into a permanent fallback.

For packaged execution, test with an empty PATH, isolated `SUPPORTER_DATA_DIR`, and immutable resources. Use `RESOURCE_ROOT` only for reading; redirect COM wrappers before importing `comtypes.client`. Embedded Python ignores several environment options: keep `-B` on worker/probe invocations.

Run the meaningful checks from [development](../../../docs/DEVELOPMENT.md). For cross-boundary changes, obtain an independent frontend/backend/release test pass when subagents are available. Assign different files, integrate failures, and rerun only checks justified by changes. Report fixture substitutions and skipped foreground tests precisely.
