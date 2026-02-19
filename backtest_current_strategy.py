#!/usr/bin/env python3
"""Compatibility entrypoint for current strategy backtests.

Use scripts/backtest_v3_detailed.py for the detailed simulator.
"""

import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parent
    script = root / "scripts" / "backtest_v3_detailed.py"
    if not script.exists():
        print("Missing scripts/backtest_v3_detailed.py")
        return 1

    cmd = [sys.executable, str(script)]
    if len(sys.argv) > 1:
        cmd.extend(sys.argv[1:])
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
