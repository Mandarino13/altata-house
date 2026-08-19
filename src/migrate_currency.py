#!/usr/bin/env python3
"""One-off migration: retrofit budget.yml with original_amount + currency + amount_usd."""
import sys
sys.path.insert(0, "/Users/gerardolozano/altata-house/src")
import os
import yaml
from tracker import convert_to_usd, save_data, export_to_csv

DATA = os.path.expanduser("~/altata-house/data/budget.yml")

# Map each entry (date, notes) -> (original_amount, currency)
# User confirmed: Visa = USD, all Japan items = JPY, rest = MXN
CURRENCY_MAP = {
    ("2026-06-02", "Initial savings deposit"): (50.0, "MXN"),
    ("2026-06-02", "Matched initial savings"): (50.0, "MXN"),
    ("2026-06-03", "Mac credit"): (45000.0, "MXN"),
    ("2026-06-03", "Football shirt and shoes"): (4000.0, "MXN"),
    ("2026-06-03", "Table"): (2999.0, "MXN"),
    ("2026-06-03", "test dinner"): (1000.0, "MXN"),
    ("2026-06-07", "Breakfast with parents"): (1700.0, "MXN"),
    ("2026-08-04", "Visa fee lent by Kristina"): (200.0, "USD"),
    ("2026-08-13", "Muji"): (8650.0, "MXN"),
    ("2026-08-14", "Japan shirt for brother William (19,000 JPY)"): (19000.0, "JPY"),
    ("2026-08-14", "tshirts for Gerardo (11,000 JPY)"): (11000.0, "JPY"),
    ("2026-08-14", "Beam jacket (11,000 JPY)"): (11000.0, "JPY"),
    ("2026-08-14", "Liverpool shirt"): (6650.0, "JPY"),   # bought in Japan
    ("2026-08-14", "Cameras (11,637 JPY)"): (11637.0, "JPY"),
    ("2026-08-14", "Yen purchase (22,000 JPY)"): (22000.0, "JPY"),
}

with open(DATA) as f:
    data = yaml.safe_load(f)

new_entries = []
unmapped = []
for e in data.get("entries", []):
    key = (e.get("date"), e.get("notes"))
    if key in CURRENCY_MAP:
        orig, cur = CURRENCY_MAP[key]
    else:
        unmapped.append(key)
        continue
    e["original_amount"] = orig
    e["currency"] = cur
    e["amount_usd"] = convert_to_usd(orig, cur)
    # drop legacy value field
    e.pop("value", None)
    new_entries.append(e)

if unmapped:
    print("UNMAPPED entries (skipped):", unmapped)
    sys.exit(1)

data["entries"] = new_entries
save_data("budget", data)
export_to_csv("budget")
print(f"Migrated {len(new_entries)} entries.")
for e in new_entries:
    print(f"  {e['date']} {e['actor']:8} {e['original_amount']:>10,.2f} {e['currency']:3} -> ${e['amount_usd']:>10,.2f}  {e['notes'][:50]}")
