#!/usr/bin/env python3
"""Script simples para simular a exportação pública do ranking."""
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from utils.database_manager import db_manager


async def main():
    snapshot = await db_manager.get_ranking_snapshot(5)
    print(json.dumps(snapshot, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    asyncio.run(main())
