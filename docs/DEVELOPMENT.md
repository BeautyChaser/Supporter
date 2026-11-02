# Development and verification

Use Windows x64, Node.js 22.12+, Python 3.11+ and Windows PowerShell.

```powershell
npm ci
python -m pip install --target .vendor -r requirements.txt
New-Item -ItemType Directory -Force .runtime
powershell -NoProfile -ExecutionPolicy Bypass -File build-native.ps1
npm run check
python -m unittest discover -s tests -q
node tests/completion.cjs
node tests/completion-store.cjs
powershell -NoProfile -ExecutionPolicy Bypass -File tests/run-frontend.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File tests/run-onboarding.ps1
```

start.ps1 runs the development version. Never copy developer settings into defaults/settings.json.

`npm run dist:dir` builds an unpacked app; `npm run dist:win` builds installer/ZIP under release/. Stage is build/payload. Users need none of these build tools.

Core tests use owned CLI fixtures; Electron tests isolate data/Chromium profiles. Native tests verify their fixture HWND and foreground and skip on mismatch. live_* account-backed scripts are opt-in and excluded from CI.

Run `python tests/packaged_smoke.py --help` for embedded-runtime checks. Use built release/win-unpacked/resources/supporter with isolated data/home/plugin paths and an ignored report destination.

Read [AGENTS.md](../AGENTS.md). Skills are in .agents/skills; roles in .codex/agents inherit the caller's permissions/model. `python scripts/validate-agent-kit.py` validates the kit. No singular .agent directory is used.
