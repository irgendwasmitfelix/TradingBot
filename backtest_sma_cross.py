import pandas as pd
import numpy as np
from datetime import datetime

# Load data
df = pd.read_csv('/tmp/ACTEUR.csv', header=None, names=['ts', 'price', 'vol'], dtype={'ts': int, 'price': float, 'vol': float})
df['datetime'] = pd.to_datetime(df['ts'], unit='s')
df.set_index('datetime', inplace=True)

# Resample to 1h OHLC
ohlc = df['price'].resample('1h').ohlc()

# Compute SMA 20 on close
ohlc['sma20'] = ohlc['close'].rolling(window=20).mean()

# Find crosses: buy when close crosses above sma20
ohlc['signal'] = np.where((ohlc['close'].shift(1) < ohlc['sma20'].shift(1)) & (ohlc['close'] > ohlc['sma20']), 'BUY', 'HOLD')

# Simple backtest: buy at close, sell after 24H
results = []
position = None
for idx, row in ohlc.iterrows():
    if row['signal'] == 'BUY' and position is None:
        position = {'entry_price': row['close'], 'entry_time': idx}
    elif position and (idx - position['entry_time']).total_seconds() > 24*3600:
        pnl = (row['close'] - position['entry_price']) / position['entry_price'] * 100
        results.append(pnl)
        position = None

print(f'Number of trades: {len(results)}')
if results:
    print(f'Average PNL: {np.mean(results):.2f}%')
    print(f'Win rate: {sum(1 for r in results if r > 0) / len(results) * 100:.2f}%')