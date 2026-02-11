#!/usr/bin/env python3
import json
from pathlib import Path

REPORT = Path("reports/prod_dev_yearly_detailed.json")
OUT = Path("reports/release_gate_prod_dev.json")

if not REPORT.exists():
    raise SystemExit("Missing reports/prod_dev_yearly_detailed.json. Run yearly backtest first.")

data = json.loads(REPORT.read_text())
prod = data["prod"]
dev = data["dev"]

checks = {
    "dev_return_better_than_prod": dev["return_pct"] > prod["return_pct"],
    "dev_drawdown_not_worse_than_prod": dev["max_drawdown_pct"] <= prod["max_drawdown_pct"],
    "dev_final_capital_higher": dev["final_eur"] > prod["final_eur"],
}

passed = all(checks.values())
out = {
    "period": data["period"],
    "passed": passed,
    "checks": checks,
    "prod": prod,
    "dev": dev,
}
OUT.write_text(json.dumps(out, indent=2))
print(json.dumps(out, indent=2))
