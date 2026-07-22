from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bot.replay import ReplayValidationError, read_bundle


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a Tien Len replay bundle.")
    parser.add_argument("replay", type=Path)
    args = parser.parse_args()
    try:
        bundle = read_bundle(args.replay)
    except ReplayValidationError as exc:
        print(f"INVALID {exc}")
        return 2
    print(
        f"VALID schema={bundle.schema_version} bot={bundle.bot_id} "
        f"session={bundle.session_id} events={len(bundle.events)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
