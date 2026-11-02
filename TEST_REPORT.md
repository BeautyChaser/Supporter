# Verification

Fixture tests, real packaged-runtime checks and optional account-backed benchmarks are separate. Machine-specific logs/reports remain ignored under .runtime/.

Coverage includes command/result/environment validation, terminal/source checks, multiline and clipboard fallback; CLI reuse/reasoning/retry/cancel/route isolation; plugin add/remove/cache/fallback; real Electron keyboard/settings/welcome flows; personal completion persistence/privacy; and actual embedded Python under empty PATH with immutable resources.

Distribution checks inspect file allowlists/hashes, clean defaults, actual ASAR and resources. See [development](docs/DEVELOPMENT.md), tests/packaged_smoke.py, tests/test_release_manifest.py and the Electron harness runners for reproduction.

Native checks exercise owned HWND fixtures, not user terminals/documents. Skipped foreground tests are not successes. Remote/TUI/special key bindings can need clipboard fallback. Model metadata does not guarantee account access or fixed latency. Native Acrylic requires Windows 11 22H2+. Packages are unsigned and not tested on every physical Windows configuration.
