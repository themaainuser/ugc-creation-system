"""Load ugc-system/.env into os.environ (real env vars always win)."""
from __future__ import annotations

import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # ugc-system/


def parse_env_file(text: str) -> dict[str, str]:
    """KEY=VALUE lines; '#' comments; ' //' starts an inline comment."""
    vals: dict[str, str] = {}
    for line in text.splitlines():
        line = re.split(r"\s+//", line, maxsplit=1)[0].strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        vals[k.strip()] = v.strip().strip('"').strip("'")
    return vals


def load_env(path: Path | None = None) -> None:
    env_file = path or ROOT / ".env"
    if not env_file.exists():
        return
    for k, v in parse_env_file(env_file.read_text(encoding="utf-8")).items():
        if v:
            os.environ.setdefault(k, v)
