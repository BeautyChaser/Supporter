# Architecture

| Boundary | Ownership |
| --- | --- |
| desktop/main.cjs | Tray, hotkey, windows, source capture, worker IPC and appearance. |
| desktop/renderer.js | Conversation, branches, slash commands and request-correlated state. |
| settings/onboarding | Preferences and first-run setup; refresh preserves drafts. |
| supporter/service.py | Serial NDJSON state transitions, asynchronous detection/generation. |
| backend_plugins/adapters | Reloadable manifests, local probes/cache, invocation protocols. |
| windows/uia_native/C# | Read caret/focus, validate target, explicit acceptance. |
| completion/store | Public metadata plus separate user definitions/usage. |

`paths.py` and `runtime-paths.cjs` share SUPPORTER_RESOURCE_ROOT and SUPPORTER_DATA_DIR. Resources contain immutable code, embedded Python, dependencies and native helpers. Data owns settings, logs, request files, editable plugins and personal completion JSON.

Development defaults to the checkout. Installed apps use per-user Electron data. Explicit overrides initialize clean defaults and never import source-private settings. Embedded Python uses -B and explicit _pth paths; COM code generation is redirected before importing comtypes.client. Bundled native helpers take priority over developer manifests.

Capture the source before helper focus. Blur hides; Esc ends context. Generation/capture request IDs reject stale events. Explanations never become replacement text. Backend checking preserves preference until confirmed failure; fallback preserves active requests and candidates.

Build allowlists are electron-builder.cjs (ASAR) and scripts/prepare-runtime.py (payload). User state and test fixtures are not application resources.
