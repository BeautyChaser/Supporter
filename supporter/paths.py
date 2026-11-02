"""Separate immutable application resources from writable per-user state."""
import os
from pathlib import Path

SOURCE_ROOT=Path(__file__).resolve().parent.parent
RESOURCE_ROOT=Path(os.environ.get('SUPPORTER_RESOURCE_ROOT') or SOURCE_ROOT).resolve()
DATA_ROOT=Path(os.environ.get('SUPPORTER_DATA_DIR') or SOURCE_ROOT).resolve()
RUNTIME_ROOT=DATA_ROOT/'.runtime'
VENDOR_ROOT=RESOURCE_ROOT/'.vendor'
NATIVE_ROOT=RESOURCE_ROOT/'native'

def ensure_runtime():
    RUNTIME_ROOT.mkdir(parents=True,exist_ok=True)
    return RUNTIME_ROOT

def helper_path(name):
    bundled=NATIVE_ROOT/(name+'.exe')
    if bundled.is_file():return bundled
    manifest=RUNTIME_ROOT/('paste-path.txt' if name=='paste-bridge' else 'caret-path.txt')
    if manifest.is_file():
        candidate=Path(manifest.read_text(encoding='utf-8-sig').strip())
        if candidate.is_file():return candidate
    fallback=RUNTIME_ROOT/(name+'.exe')
    return fallback if fallback.is_file() else None
