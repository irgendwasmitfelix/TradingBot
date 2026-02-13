# Minimal price-action helpers for bar pattern detection

from typing import List, Tuple


def wick_ratio(candle: Tuple[float,float,float,float]) -> float:
    # candle = (open, high, low, close)
    o,h,l,c = candle
    body = abs(c - o)
    upper = h - max(c,o)
    lower = min(c,o) - l
    if body <= 0:
        return 0.0
    return (upper + lower) / body


def two_bar_pattern(prev: Tuple[float,float,float,float], cur: Tuple[float,float,float,float]) -> str:
    # simple engulfing / continuation detection
    po,ph,pl,pc = prev
    o,h,l,c = cur
    # bullish engulf
    if c > o and pc < po and c > ph and o < pl:
        return 'BULL_ENGULF'
    if c < o and pc > po and c < pl and o > ph:
        return 'BEAR_ENGULF'
    return 'NONE'


def three_bar_pattern(bars: List[Tuple[float,float,float,float]]) -> str:
    if len(bars) < 3:
        return 'NONE'
    p2,p1,c = bars[-3],bars[-2],bars[-1]
    # simple pattern: two small bars then big breakout
    b2 = abs(p2[3]-p2[0])
    b1 = abs(p1[3]-p1[0])
    b0 = abs(c[3]-c[0])
    if b2 < b0*0.5 and b1 < b0*0.5 and c[3] > c[0]:
        return 'BREAKOUT_UP'
    if b2 < b0*0.5 and b1 < b0*0.5 and c[3] < c[0]:
        return 'BREAKOUT_DOWN'
    return 'NONE'
