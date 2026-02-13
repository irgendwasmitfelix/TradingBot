import pandas as pd
import numpy as np
from datetime import datetime

# Load data
df = pd.read_csv('/tmp/ACTEUR.csv', header=None, names=['ts', 'price', 'vol'], dtype={'ts': int, 'price': float, 'vol': float})
df['datetime'] = pd.to_datetime(df['ts'], unit='s')
df.set_index('datetime', inplace=True)

# Resample to 1h
ohlc = df['price'].resample('1h').ohlc()

# Compute hourly return
ohlc['return'] = ohlc['close'].pct_change()

# Group by hour of day
ohlc['hour'] = ohlc.index.hour
hourly_avg_return = ohlc.groupby('hour')['return'].mean()

print("Average return by hour of day (UTC):")
for hour in range(24):
    avg_ret = hourly_avg_return.get(hour, 0) * 100
    print(f"{hour:2d}: {avg_ret:.2f}%")

# Find best hours to buy, e.g., buy at hour with low return, sell next.

# Simple: buy at 9am UTC, sell at 10am
buy_hour = 9
sell_hour = 10

trades = []
position = None
for idx, row in ohlc.iterrows():
    if row['hour'] == buy_hour and position is None:
        position = {'entry_price': row['close'], 'entry_time': idx}
    elif position and row['hour'] == sell_hour:
        pnl = (row['close'] - position['entry_price']) / position['entry_price'] * 100
        trades.append(pnl)
        position = None

print(f"\nBuy at {buy_hour}, sell at {sell_hour}:")
print(f'Number of trades: {len(trades)}')
if trades:
    print(f'Average PNL: {np.mean(trades):.2f}%')
    print(f'Win rate: {sum(1 for r in trades if r > 0) / len(trades) * 100:.2f}%')