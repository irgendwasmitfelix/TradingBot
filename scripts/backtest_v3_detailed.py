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
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple

import numpy as np
import requests

PAIRS = ["XXBTZEUR", "XETHZEUR", "SOLEUR", "ADAEUR", "DOTEUR", "XXRPZEUR", "LINKEUR"]


@dataclass
class Position:
    side: int = 0  # 1 long, -1 short
    qty: float = 0.0
    entry_price: float = 0.0
    entry_ts: int = 0
    tag: str = ""


def fetch_ohlc(pair: str, since_ts: int, interval: int = 60) -> Dict[int, float]:
    r = requests.get(
        "https://api.kraken.com/0/public/OHLC",
        params={"pair": pair, "interval": interval, "since": since_ts},
        timeout=20,
    )
    j = r.json()
    if j.get("error"):
        raise RuntimeError(f"Kraken error for {pair}: {j['error']}")
    key = [k for k in j["result"].keys() if k != "last"][0]
    return {int(x[0]): float(x[4]) for x in j["result"][key]}


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
    rsi = calc_rsi(prices, 14)
    if rsi is None:
        return "HOLD", 0.0
    sma20 = float(np.mean(prices[-20:]))
    sma50 = float(np.mean(prices[-50:]))
    recent = np.array(prices[-20:])
    vol_pct = float(np.std(recent) / np.mean(recent) * 100) if np.mean(recent) > 0 else 0.0
    if vol_pct < 0.15:
        return "HOLD", 0.0

    rsi_score = 0.0
    if rsi < 30:
        rsi_score = (30 - rsi) / 30 * 50
    elif rsi > 70:
        rsi_score = -((rsi - 70) / 30 * 50)

    sma_score = max(-50.0, min(50.0, (((sma20 - sma50) / sma50) * 100) * 10))
    total = rsi_score + sma_score
    ratio = (sma20 - sma50) / sma50

    # mean reversion
    if rsi < 33 and ratio > -0.003:
        return "BUY", total
    if rsi > 67 and ratio < 0.003:
        return "SELL", total
    # trend continuation
    if ratio > 0.006 and 45 <= rsi <= 68:
        return "BUY", total + 8
    if ratio < -0.006 and 32 <= rsi <= 55:
        return "SELL", total - 8
    return "HOLD", total


def run_backtest(days: int, initial_eur: float, fee_rate: float, slippage_bps: float) -> dict:
    since = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp())
    series = {p: fetch_ohlc(p, since, 60) for p in PAIRS}
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

            tp = 1.2 if position.tag == "scalp" else 6.0
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

        # direction switch logic
        is_scalp = abs(sc) >= 28
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

    result = {
        "period_days": days,
        "initial_eur": round(initial_eur, 2),
        "final_eur": round(cash, 2),
        "return_pct": round((cash - initial_eur) / initial_eur * 100, 2),
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
