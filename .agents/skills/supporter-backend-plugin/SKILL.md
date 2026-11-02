---
name: supporter-backend-plugin
description: Add or repair a self-detecting Supporter CLI backend plugin, its model and reasoning capabilities, invocation and output mapping.
---

Read [plugin contract](../../../backend-plugins/README.md). Prefer a declarative `adapter: generic` manifest for noninteractive native CLIs; reuse a built-in adapter when its protocol matches. Add adapter code only for protocols the generic mapping cannot express.

Detection commands use fixed argv. Generation templates are replaced once; inserted prompt text stays data. Preserve Unicode, quoting and multiline input. Generic batch/PowerShell launchers are rejected; declare the actual executable or fixed interpreter/script entry.

Probe availability separately from model/account permissions. Preserve useful cached metadata on transient failure and mark it stale. A broken plugin must not prevent the others from working.

Run `tests/test_backend_plugins.py` and `tests/test_backend_lifecycle.py` with owned fixtures, covering add/remove/disable, executable removal/reinstallation, bad versions, capabilities, cache invalidation and actual fixture stdin/argv/output. Do not exercise installed account-backed CLIs without authorization.

To ship a new bundled plugin, add it to the explicit `PLUGINS` list in `scripts/prepare-runtime.py` and release tests. User-installed manifests belong to the data directory and are never swept into a distribution.
