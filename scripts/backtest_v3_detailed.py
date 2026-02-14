#!/usr/bin/env python3
"""Detailed V3 backtest estimator (long+short capable simulation layer).

Notes:
- Uses Kraken OHLC 1h data.
- Includes fees + configurable slippage.
- Simulates regime switching, multi-edge entries, risk guards, long/short engine.
- This is a research simulator, not live-order execution code.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import requests

PAIRS = ["XXBTZEUR", "XETHZEUR", "SOLEUR", "ADAEUR", "DOTEUR", "XXRPZEUR", "LINKEUR"]
# Allow overriding the cache directory from the environment so external runners (autosim)
# can populate OHLC data there and avoid live Kraken requests.
CACHE_DIR = Path(os.getenv("BACKTEST_CACHE_DIR", "data/ohlc_cache"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)
# Local timesales directory (optional)
LOCAL_TS_DIR = Path(os.getenv("KRAKEN_TS_DIR", "/mnt/fritz_nas/Volume/kraken_daten/TimeAndSales_Combined"))
USE_LOCAL_TS = os.getenv("USE_LOCAL_TS", "1") == "1"

# Backtest tunables via env (override defaults for experiments/sweeps)
BACKTEST_SWING_TP = float(os.getenv('BACKTEST_TP_SWING', '6.0'))
BACKTEST_SCALP_TP = float(os.getenv('BACKTEST_TP_SCALP', '1.2'))
BACKTEST_MIN_SCORE = float(os.getenv('BACKTEST_MIN_SCORE', '0.0'))


@dataclass
class Position:
    side: int = 0  # 1 long, -1 short
    qty: float = 0.0
    entry_price: float = 0.0
    entry_ts: int = 0
    tag: str = ""


def _pair_file_candidates(pair: str) -> List[str]:
    clean = pair.replace("Z", "")
    return [f"{pair}.csv", f"{clean}.csv", f"{clean.replace('XXBT', 'XBT')}.csv"]


def load_local_timesales_ohlc(pair: str, since_ts: int, end_ts: int, interval: int = 60) -> Dict[int, float]:
    if not LOCAL_TS_DIR.exists():
        return {}
    fpath = None
    for name in _pair_file_candidates(pair):
        p = LOCAL_TS_DIR / name
        if p.exists():
            fpath = p
            break
    if fpath is None:
        return {}

    bucket = max(1, int(interval)) * 60
    out: Dict[int, float] = {}
    seen_window = False
    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            parts = line.strip().split(",")
            if len(parts) < 2:
                continue
            try:
                ts = int(float(parts[0]))
                px = float(parts[1])
            except Exception:
                continue
            if ts < since_ts:
                continue
            if ts > end_ts:
                if seen_window:
                    break
                continue
            seen_window = True
            bts = (ts // bucket) * bucket
            out[bts] = px  # last price in bucket
    return out


def fetch_ohlc(pair: str, since_ts: int, end_ts: int, interval: int = 60) -> Dict[int, float]:
    cache_path = CACHE_DIR / f"{pair}_{since_ts}_{end_ts}_{interval}m.json"
    if cache_path.exists():
        return {int(k): float(v) for k, v in json.loads(cache_path.read_text()).items()}

    if USE_LOCAL_TS:
        local = load_local_timesales_ohlc(pair, since_ts, end_ts, interval)
        if local:
            cache_path.write_text(json.dumps(local))
            return local

    out: Dict[int, float] = {}
    since = since_ts
    sess = requests.Session()
    loops = 0

    while since < end_ts and loops < 500:
        loops += 1
        for attempt in range(8):
            r = sess.get(
                "https://api.kraken.com/0/public/OHLC",
                params={"pair": pair, "interval": interval, "since": since},
                timeout=30,
            )
            j = r.json()
            errs = j.get("error") or []
            if errs and any("Too many requests" in e for e in errs):
                time.sleep(1.5 + attempt * 1.0)
                continue
            if errs:
                raise RuntimeError(f"Kraken error for {pair}: {errs}")
            break
        else:
            raise RuntimeError(f"Kraken rate-limit retries exhausted for {pair}")

        res = j.get("result", {})
        key = [k for k in res.keys() if k != "last"]
        if not key:
            break
        rows = res[key[0]]
        if not rows:
            break

        last_ts = since
        for row in rows:
            ts = int(row[0])
            if since_ts <= ts <= end_ts:
                out[ts] = float(row[4])
            last_ts = max(last_ts, ts)

        nxt = int(res.get("last", last_ts + 1))
        since = nxt if nxt > since else (last_ts + 1)
        time.sleep(0.35)

    cache_path.write_text(json.dumps(out))
    return out


def calc_rsi(prices: List[float], period: int = 14) -> float | None:
    if len(prices) < period + 1:
        return None
    arr = np.array(prices)
    deltas = np.diff(arr)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 0.0
    rs = avg_gain / avg_loss
    return float(100 - (100 / (1 + rs)))


def strategy_signal(prices: List[float]) -> Tuple[str, float]:
    if len(prices) < 50:
        return "HOLD", 0.0

    # Data extraction
    current_price = prices[-1]
    prices_arr = np.array(prices)

    # Indicators
    sma20 = np.mean(prices_arr[-20:])
    std20 = np.std(prices_arr[-20:])
    sma50 = np.mean(prices_arr[-50:])

    upper_bb = sma20 + (2.0 * std20)
    lower_bb = sma20 - (2.0 * std20)

    # Strategy: Bollinger Band Breakout (John Carter / Al Brooks style)
    # We want to catch the expansion.

    signal = "HOLD"
    score = 0.0

    if current_price > upper_bb:
        # Bullish Breakout
        # Filter: Long-term trend must be up (Price > SMA50)
        if current_price > sma50:
            signal = "BUY"
            # Score based on strength of breakout
            breakout_pct = ((current_price - upper_bb) / upper_bb) * 100
            score = 25.0 + (breakout_pct * 50.0)  # Start at 25, add boost

    elif current_price < lower_bb:
        # Bearish Breakout
        # Filter: Long-term trend must be down (Price < SMA50)
        if current_price < sma50:
            signal = "SELL"
            breakout_pct = ((lower_bb - current_price) / lower_bb) * 100
            score = -25.0 - (breakout_pct * 50.0)  # Start at -25, add boost

    # Cap score
    score = max(-50.0, min(50.0, score))

    return signal, score


def run_backtest(days: int, initial_eur: float, fee_rate: float, slippage_bps: float) -> dict:
    end_ts = int(datetime.now(timezone.utc).timestamp())
    since = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp())
    series = {p: fetch_ohlc(p, since, end_ts, 60) for p in PAIRS}
    all_ts = sorted(set().union(*[set(v.keys()) for v in series.values()]))

    hist = {p: deque(maxlen=80) for p in PAIRS}
    signal = {p: "HOLD" for p in PAIRS}
    score = {p: 0.0 for p in PAIRS}
    price = {p: 0.0 for p in PAIRS}
    pos = {p: Position() for p in PAIRS}

    cash = initial_eur
    last_trade_ts = 0
    consecutive_losses = 0
    pause_until = 0
    closed = []
    peak_eq = initial_eur
    min_eq = initial_eur
    max_dd = 0.0
    bars_total = 0
    bars_above_initial = 0
    bars_below_initial = 0

    def equity() -> float:
        eq = cash
        for p in PAIRS:
            px = price.get(p, 0.0)
            position = pos[p]
            if position.side == 1:
                eq += position.qty * px
            elif position.side == -1:
                eq += (position.entry_price - px) * position.qty
        return eq

    for ts in all_ts:
        for p in PAIRS:
            px = series[p].get(ts)
            if px is None:
                continue
            price[p] = px
            hist[p].append(px)
            s, sc = strategy_signal(list(hist[p]))
            signal[p] = s
            score[p] = sc

        benchmark_score = score.get("XXBTZEUR", 0.0)
        risk_on = benchmark_score >= -12.0

        eq_now = equity()
        bars_total += 1
        if eq_now >= initial_eur:
            bars_above_initial += 1
        else:
            bars_below_initial += 1
        peak_eq = max(peak_eq, eq_now)
        min_eq = min(min_eq, eq_now)
        if peak_eq > 0:
            max_dd = max(max_dd, ((peak_eq - eq_now) / peak_eq) * 100.0)

        # Portfolio-level kill-switch: if drawdown is deep, cool off for 24h.
        if max_dd >= 18.0:
            pause_until = max(pause_until, ts + 24 * 3600)

        # exits first
        for p in PAIRS:
            position = pos[p]
            px = price.get(p, 0.0)
            if position.side == 0 or px <= 0:
                continue
            held_hours = (ts - position.entry_ts) / 3600 if position.entry_ts else 0
            if position.side == 1:
                pnl_pct = ((px - position.entry_price) / position.entry_price) * 100
            else:
                pnl_pct = ((position.entry_price - px) / position.entry_price) * 100

            tp = BACKTEST_SCALP_TP if position.tag == "scalp" else BACKTEST_SWING_TP
            sl = -0.8 if position.tag == "scalp" else -3.0
            max_hold_h = 6 if position.tag == "scalp" else 48

            if pnl_pct >= tp or pnl_pct <= sl or held_hours >= max_hold_h:
                slip = slippage_bps / 10000.0
                if position.side == 1:
                    exit_px = px * (1 - slip)
                    gross = position.qty * exit_px
                    fee = gross * fee_rate
                    pnl_eur = (exit_px - position.entry_price) * position.qty - fee
                    cash += gross - fee
                else:
                    exit_px = px * (1 + slip)
                    notional = position.qty * position.entry_price
                    pnl_eur = (position.entry_price - exit_px) * position.qty
                    fee = (position.qty * exit_px) * fee_rate
                    cash += notional + pnl_eur - fee

                closed.append({"pair": p, "side": position.side, "pnl_eur": pnl_eur, "tag": position.tag})
                if pnl_eur < 0:
                    consecutive_losses += 1
                    if consecutive_losses >= 3:
                        pause_until = max(pause_until, ts + 180 * 60)
                else:
                    consecutive_losses = 0
                pos[p] = Position()

        if ts - last_trade_ts < 3600:
            continue
        if ts < pause_until:
            continue

        cands = [(abs(score[p]), p) for p in PAIRS if signal[p] in ("BUY", "SELL") and pos[p].side == 0]
        if not cands:
            continue
        _, bp = max(cands)
        s = signal[bp]
        sc = score[bp]
        px = price.get(bp, 0.0)
        if px <= 0:
            continue

        # volatility targeting proxy on benchmark history
        bench_hist = list(hist.get("XXBTZEUR", []))[-20:]
        bench_vol = 0.0
        if len(bench_hist) >= 20:
            mean = float(np.mean(bench_hist))
            bench_vol = float(np.std(bench_hist) / mean * 100) if mean > 0 else 0.0
        vol_scale = 1.0 if bench_vol <= 0 else min(1.25, max(0.35, 1.6 / bench_vol))

        allocation = min(40.0, cash * 0.18) * (1.0 if risk_on else 0.60) * vol_scale
        if allocation < 8.0:
            continue

        # Fee/slippage drag gate: skip weak edges likely to be consumed by costs.
        # Round-trip drag ~= 2*fee + 2*slip (in % terms)
        rt_cost_pct = (2 * fee_rate + 2 * (slippage_bps / 10000.0)) * 100.0
        edge_est_pct = abs(sc) * 0.11  # calibrated proxy: score->expected move
        if edge_est_pct < (rt_cost_pct * 1.25):
            continue

        # direction switch logic
        is_scalp = abs(sc) >= BACKTEST_MIN_SCORE
        direction = None
        if s == "BUY" and (risk_on or is_scalp):
            direction = 1
        if s == "SELL" and ((not risk_on) or is_scalp):
            direction = -1
        if direction is None:
            continue

        slip = slippage_bps / 10000.0
        entry_px = px * (1 + slip) if direction == 1 else px * (1 - slip)
        qty = allocation / entry_px

        if direction == 1:
            total = allocation * (1 + fee_rate)
            if total > cash:
                continue
            cash -= total
        else:
            # reserve short notional from cash (conservative margin model)
            if allocation > cash:
                continue
            cash -= allocation

        pos[bp] = Position(side=direction, qty=qty, entry_price=entry_px, entry_ts=ts, tag=("scalp" if is_scalp else "swing"))
        last_trade_ts = ts

    # liquidate at end
    for p in PAIRS:
        position = pos[p]
        px = price.get(p, 0.0)
        if position.side == 0 or px <= 0:
            continue
        slip = slippage_bps / 10000.0
        if position.side == 1:
            exit_px = px * (1 - slip)
            gross = position.qty * exit_px
            fee = gross * fee_rate
            pnl_eur = (exit_px - position.entry_price) * position.qty - fee
            cash += gross - fee
        else:
            exit_px = px * (1 + slip)
            notional = position.qty * position.entry_price
            pnl_eur = (position.entry_price - exit_px) * position.qty
            fee = (position.qty * exit_px) * fee_rate
            cash += notional + pnl_eur - fee
        closed.append({"pair": p, "side": position.side, "pnl_eur": pnl_eur, "tag": position.tag})

    wins = sum(1 for x in closed if x["pnl_eur"] > 0)
    losses = sum(1 for x in closed if x["pnl_eur"] <= 0)
    pnl_sum = sum(x["pnl_eur"] for x in closed)

    by_pair = defaultdict(float)
    for x in closed:
        by_pair[x["pair"]] += x["pnl_eur"]

    above_pct = (bars_above_initial / bars_total * 100.0) if bars_total else 0.0
    below_pct = (bars_below_initial / bars_total * 100.0) if bars_total else 0.0

    result = {
        "period_days": days,
        "initial_eur": round(initial_eur, 2),
        "final_eur": round(cash, 2),
        "return_pct": round((cash - initial_eur) / initial_eur * 100, 2),
        "max_drawdown_pct": round(max_dd, 2),
        "peak_equity_eur": round(peak_eq, 2),
        "min_equity_eur": round(min_eq, 2),
        "time_above_initial_pct": round(above_pct, 2),
        "time_below_initial_pct": round(below_pct, 2),
        "data_points": {k: len(v) for k, v in series.items()},
        "closed_trades": len(closed),
        "wins": wins,
        "losses": losses,
        "winrate_pct": round((wins / len(closed) * 100), 2) if closed else 0.0,
        "net_pnl_eur": round(pnl_sum, 2),
        "by_pair_pnl": {k: round(v, 2) for k, v in sorted(by_pair.items())},
        "assumptions": {
            "fee_rate": fee_rate,
            "slippage_bps": slippage_bps,
            "mode": "research-estimator-long-short-scalp",
        },
    }
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--initial", type=float, default=200.0)
    ap.add_argument("--fee", type=float, default=0.0026)
    ap.add_argument("--slippage-bps", type=float, default=8.0)
    ap.add_argument("--out", type=str, default="reports/v3_backtest_detailed.json")
    args = ap.parse_args()

    result = run_backtest(args.days, args.initial, args.fee, args.slippage_bps)
    print(json.dumps(result, indent=2))
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)


if __name__ == "__main__":
    main()
