Place OHLCVT files here for 2026 backtests.

Expected structure on NAS:
/mnt/fritz_nas/Volume/kraken_daten/2026/
  ohlc/
    1m/    -> CSVs named <PAIR>_1m.csv (e.g., XXBTZEUR_1m.csv)
    5m/    -> CSVs named <PAIR>_5m.csv
    15m/   -> CSVs named <PAIR>_15m.csv
    60m/   -> CSVs named <PAIR>_60m.csv

CSV format: ts,open,high,low,close,volume,count
Timestamp in epoch seconds (UTC).

Backtester configuration:
- 30d runs will prefer /mnt/fritz_nas/Volume/kraken_daten/2026/ohlc/<resolution>/ when available.
- If files missing for a pair/resolution, the backtester falls back to TimeAndSales_Combined raw data.

When you upload files, name them exactly as above and I will pick them up automatically for the 30d backtests.
