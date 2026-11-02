# Windows release procedure

1. Update package/lock versions together. Keep defaults free of accounts, private proxies, personal model choices and habits.
2. Run relevant core/UI/welcome/path/release checks and agent-kit validation.
3. `npm run dist:win`; inspect actual ASAR/resources and distribution-manifest hashes. Test embedded Python with empty PATH and isolated state, then actual packaged first-run behavior.
4. Create SHA-256 sums for installer/ZIP and retain runtime licenses. Current packages are unsigned; no signing identities are bundled.
5. Audit Git index and binaries. Exclude settings, completion JSON, accounts, logs and generated/downloaded caches. Private developer reports stay in .runtime.
6. Publish only within the user's explicit request; existing session authorization is sufficient. Verify owner/remote history, push without force, create a matching tag, upload validated artifacts and verify public links.

scripts/github-release.py uses existing GitHub CLI or Git credential-manager authentication in memory. Mutations require --publish and verify the account owner. Credentials are never printed or stored in the project.

The Windows CI builds/tests the project. Trusted code signing and automatic application updates are separate capabilities and must not be claimed without implementation.
