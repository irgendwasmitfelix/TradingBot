#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime

PAIRS = ["XXBTZEUR", "XETHZEUR", "SOLEUR", "ADAEUR", "DOTEUR", "XXRPZEUR", "LINKEUR"]
INTERVALS = [1, 15, 60]
BASE = Path('/mnt/fritz_nas/Volume/kraken_research_data')


def human_size(n: int) -> str:
    units = ['B', 'KB', 'MB', 'GB']
    f = float(n)
    for u in units:
        if f < 1024 or u == units[-1]:
            return f"{f:.1f}{u}"
        f /= 1024
    return f"{n}B"


def main():
    total = len(PAIRS) * len(INTERVALS)
    done = 0
    rows = []

    for p in PAIRS:
        for i in INTERVALS:
            fp_legacy = BASE / p / f"ohlc_{i}m_5y.csv.gz"
            fp_new = BASE / p / f"ohlc_{i}m.csv"
            fp = fp_new if fp_new.exists() else fp_legacy
            exists = fp.exists()
            size = fp.stat().st_size if exists else 0
            mtime = datetime.fromtimestamp(fp.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S') if exists else '-'
            if exists and size > 1024:
                done += 1
            rows.append((p, i, 'OK' if exists else 'PENDING', human_size(size), mtime))

    print(f"Research path: {BASE}")
    print(f"Progress: {done}/{total} files ({(done/total*100):.1f}%)")
    print('-' * 88)
    print(f"{'PAIR':<10} {'INT':<5} {'STATUS':<10} {'SIZE':<10} {'UPDATED'}")
    print('-' * 88)
    for r in rows:
        print(f"{r[0]:<10} {str(r[1])+'m':<5} {r[2]:<10} {r[3]:<10} {r[4]}")

    clog = BASE / 'collector.log'
    if clog.exists():
        print('\nLast collector log lines:')
        print('-' * 88)
        try:
            lines = clog.read_text(errors='ignore').splitlines()[-10:]
            for ln in lines:
                print(ln)
        except OSError as e:
            print(f"(log currently unavailable: {e})")


if __name__ == '__main__':
    main()
