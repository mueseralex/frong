#!/usr/bin/env python3
"""Upload Frong activity CSV to Dune under namespace frong_ai / table frong_activity.

  DUNE_API_KEY=... python sync_dune.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from db import init_db  # noqa: E402
from tools.dune import activity_snapshot, cache_snapshot_file, upload_to_dune  # noqa: E402


async def main() -> None:
    init_db()
    snap = activity_snapshot()
    path = cache_snapshot_file(snap)
    print(f"snapshot -> {path}")
    result = await upload_to_dune()
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
