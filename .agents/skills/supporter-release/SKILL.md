---
name: supporter-release
description: Prepare, build, audit and publish an explicitly requested Supporter Windows distribution or GitHub release.
---

Read [release guide](../../../docs/RELEASING.md) and [AGENTS.md](../../../AGENTS.md). Prepare concrete artifacts: clean defaults, consistent version/lockfile, passing relevant tests, installer/ZIP and checksums.

Use `npm run dist:win`. Inspect `electron-builder.cjs`, `scripts/prepare-runtime.py`, the distribution manifest and actual ASAR/resources. Exclude personal settings, habits, credentials, logs, caches and generated COM wrappers. Retain runtime licenses.

Validate the built embedded Python with empty PATH and isolated data/home/plugin directories, including COM cache/native helpers. Test actual packaged startup and first-run behavior. Preserve state on upgrades. Distinguish fixture checks from live account calls; report unsigned packages as unsigned.

Publish only within an explicit user request already present in the session. Existing authorization is sufficient; building alone does not grant publication rights. Verify owner/repository and staged source, push without force, upload validated artifacts and verify public asset links. Use normal existing authentication without printing credentials. Stop on owner mismatch or conflicting history rather than overwriting it.
