#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime

REPORT_DIR = Path('/home/felix/TradingBot/reports/sim')
OUT = Path('/home/felix/TradingBot/reports/health_summary.txt')

now = datetime.utcnow().isoformat()
summary = {'generated': now, 'runs': []}

for f in sorted(REPORT_DIR.glob('*.json')):
    try:
        j = json.load(open(f))
    except Exception:
        continue
    summary['runs'].append({
        'file': str(f.name),
        'period_days': j.get('period_days'),
        'initial': j.get('initial_eur'),
        'final': j.get('final_eur'),
        'return_pct': j.get('return_pct'),
        'max_drawdown_pct': j.get('max_drawdown_pct'),
        'sharpe': j.get('metrics', {}).get('sharpe'),
        'calmar': j.get('metrics', {}).get('calmar'),
    })

OUT.parent.mkdir(parents=True, exist_ok=True)
with open(OUT, 'w') as fo:
    fo.write('Health Summary\n')
    fo.write('Generated: %s\n\n' % now)
    for r in summary['runs']:
        fo.write(f"File: {r['file']}\n")
        fo.write(f"  Period days: {r['period_days']}\n")
        fo.write(f"  Initial: {r['initial']} Final: {r['final']} Return%: {r['return_pct']} MDD%: {r['max_drawdown_pct']}\n")
        fo.write(f"  Sharpe: {r['sharpe']} Calmar: {r['calmar']}\n\n")

print('Wrote', OUT)
