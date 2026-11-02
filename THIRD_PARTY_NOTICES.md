# Third-party components

The Windows distribution includes the following unmodified runtimes and libraries:

- Electron and Chromium: license files are shipped alongside the application (`LICENSE.electron.txt` / `LICENSES.chromium.html`, depending on the packager).
- CPython 3.14.8, Python Software Foundation License and included third-party notices: `resources/supporter/python/LICENSE.txt`.
- comtypes 1.4.17, MIT License: `resources/supporter/.vendor/comtypes-1.4.17.dist-info/licenses/LICENSE.txt` (or the license file in that distribution's metadata).

Build tools are development dependencies and are not application runtime code. Their own licenses remain with their respective packages. AI backend CLIs are detected on the user's machine and are not bundled with Supporter.
