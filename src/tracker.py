#!/usr/bin/env python3
"""Altata House Tracker — multi-currency ledger.

Each entry stores:
  original_amount : amount in the currency it was spent
  currency        : ISO code (MXN, JPY, USD)
  amount_usd      : converted value in USD (secondary/general column)

Run: python3 tracker.py --help
"""
import os
import sys
import yaml
import csv
import json
import urllib.request
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
CSV_DIR = os.path.join(DATA_DIR, 'csv')
REPORTS_DIR = os.path.join(BASE_DIR, 'reports')

# Configured Entities
VALID_ACTORS = ["Gerardo", "Kristina", "System"]
VALID_BENEFICIARIES = ["Gerardo", "Kristina", "Both"]
VALID_CURRENCIES = ["MXN", "JPY", "USD"]

# Static fallback rates (used only if the live API is unreachable)
_FALLBACK_RATES = {"MXN": 17.0, "JPY": 155.0, "USD": 1.0}
_RATES_CACHE = None


def get_rates():
    """Return {CURRENCY: units per 1 USD}. Tries live API, falls back to static."""
    global _RATES_CACHE
    if _RATES_CACHE:
        return _RATES_CACHE
    try:
        with urllib.request.urlopen(
            "https://open.er-api.com/v6/latest/USD", timeout=8
        ) as resp:
            data = json.loads(resp.read().decode())
            rates = data.get("rates", {})
            if rates.get("MXN") and rates.get("JPY"):
                _RATES_CACHE = {"MXN": rates["MXN"], "JPY": rates["JPY"], "USD": 1.0}
                return _RATES_CACHE
    except Exception:
        pass
    _RATES_CACHE = dict(_FALLBACK_RATES)
    return _RATES_CACHE


def convert_to_usd(amount, currency):
    """Convert an amount in the given currency to USD."""
    currency = currency.upper()
    if currency == "USD":
        return round(float(amount), 2)
    rates = get_rates()
    if currency not in rates:
        raise ValueError(f"Unsupported currency: {currency}")
    return round(float(amount) / rates[currency], 2)


def get_db_path(category):
    return os.path.join(DATA_DIR, f"{category}.yml")

def get_csv_path(category):
    return os.path.join(CSV_DIR, f"{category}.csv")

def load_data(category):
    path = get_db_path(category)
    if not os.path.exists(path):
        return {"entries": []}
    try:
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
            return data if data else {"entries": []}
    except Exception as e:
        print(f"Error loading {category}: {e}", file=sys.stderr)
        return {"entries": []}

def save_data(category, data):
    path = get_db_path(category)
    try:
        with open(path, 'w') as f:
            yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)
        return True
    except Exception as e:
        print(f"Error saving {category}: {e}", file=sys.stderr)
        return False

def add_entry(category, subcategory, actor, beneficiary, amount, currency, notes, date_str=None):
    if actor not in VALID_ACTORS:
        return False, f"Invalid actor: '{actor}'. Must be one of {VALID_ACTORS}"
    if beneficiary not in VALID_BENEFICIARIES:
        return False, f"Invalid beneficiary: '{beneficiary}'. Must be one of {VALID_BENEFICIARIES}"
    currency = currency.upper()
    if currency not in VALID_CURRENCIES:
        return False, f"Invalid currency: '{currency}'. Must be one of {VALID_CURRENCIES}"

    try:
        amount = float(amount)
    except ValueError:
        return False, f"Amount must be a number, got '{amount}'"

    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")
    else:
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            return False, f"Date must be in YYYY-MM-DD format, got '{date_str}'"

    # Convert to USD
    try:
        amount_usd = convert_to_usd(amount, currency)
    except ValueError as e:
        return False, str(e)

    # Load existing data
    data = load_data(category)

    entry = {
        "date": date_str,
        "actor": actor,
        "beneficiary": beneficiary,
        "subcategory": subcategory,
        "original_amount": amount,
        "currency": currency,
        "amount_usd": amount_usd,
        "notes": notes.strip()
    }

    data["entries"].append(entry)

    if save_data(category, data):
        export_to_csv(category)
        return True, entry
    return False, "Failed to save data"

def export_to_csv(category):
    data = load_data(category)
    csv_path = get_csv_path(category)
    os.makedirs(CSV_DIR, exist_ok=True)
    try:
        with open(csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["Date", "Actor", "Beneficiary", "Subcategory",
                             "Original Amount", "Currency", "Amount (USD)", "Notes"])
            for entry in data.get("entries", []):
                writer.writerow([
                    entry.get("date"),
                    entry.get("actor"),
                    entry.get("beneficiary", "Both"),
                    entry.get("subcategory"),
                    entry.get("original_amount", entry.get("value", "")),
                    entry.get("currency", ""),
                    entry.get("amount_usd", ""),
                    entry.get("notes")
                ])
        return True
    except Exception as e:
        print(f"Error exporting CSV for {category}: {e}", file=sys.stderr)
        return False

def validate_all_data():
    categories = ["budget", "houselife", "trips"]
    report = {}
    for cat in categories:
        path = get_db_path(cat)
        if not os.path.exists(path):
            report[cat] = {"status": "empty/missing"}
            continue
        data = load_data(cat)
        entries = data.get("entries", [])
        errors = []
        # Money fields only required for monetary categories (budget, trips)
        money_categories = ("budget", "trips")
        for idx, entry in enumerate(entries):
            if cat in money_categories:
                for field in ["date", "actor", "subcategory", "original_amount",
                              "currency", "amount_usd", "notes"]:
                    if field not in entry:
                        errors.append(f"Entry {idx}: Missing field '{field}'")
            else:
                for field in ["date", "actor", "subcategory", "notes"]:
                    if field not in entry:
                        errors.append(f"Entry {idx}: Missing field '{field}'")
            actor = entry.get("actor")
            if actor and actor not in VALID_ACTORS:
                errors.append(f"Entry {idx}: Invalid actor '{actor}'")
            beneficiary = entry.get("beneficiary")
            if beneficiary and beneficiary not in VALID_BENEFICIARIES:
                errors.append(f"Entry {idx}: Invalid beneficiary '{beneficiary}'")
            currency = entry.get("currency")
            if currency and currency not in VALID_CURRENCIES:
                errors.append(f"Entry {idx}: Invalid currency '{currency}'")
            value = entry.get("original_amount")
            if value is not None:
                try:
                    float(value)
                except ValueError:
                    errors.append(f"Entry {idx}: Non-numeric original_amount '{value}'")
            usd = entry.get("amount_usd")
            if usd is not None:
                try:
                    float(usd)
                except ValueError:
                    errors.append(f"Entry {idx}: Non-numeric amount_usd '{usd}'")
            date = entry.get("date")
            if date:
                try:
                    datetime.strptime(date, "%Y-%m-%d")
                except ValueError:
                    errors.append(f"Entry {idx}: Invalid date format '{date}'")
        report[cat] = {
            "status": "valid" if not errors else "invalid",
            "entry_count": len(entries),
            "errors": errors
        }
    return report

def fmt_orig(entry):
    """Format original amount + currency, e.g. '¥19,000' or '$200'."""
    amount = entry.get("original_amount", 0)
    cur = entry.get("currency", "")
    sym = {"JPY": "¥", "USD": "$", "MXN": "$"}.get(cur, "")
    if cur == "USD" or cur == "MXN":
        return f"{sym}{amount:,.2f} {cur}"
    return f"{sym}{amount:,.0f} {cur}"

def fmt_usd(amount):
    return f"${amount:,.2f}"

def get_text_summary(category):
    data = load_data(category)
    entries = data.get("entries", [])
    if not entries:
        return f"No entries found in category '{category}'."

    df = pd.DataFrame(entries)
    if 'beneficiary' not in df.columns:
        df['beneficiary'] = 'Both'
    else:
        df['beneficiary'] = df['beneficiary'].fillna('Both')
    if 'amount_usd' not in df.columns:
        df['amount_usd'] = df.get('value', 0)

    summary_lines = []
    summary_lines.append(f"📊 **Altata House — {category.upper()} SUMMARY** (in USD)")
    summary_lines.append("────────────────────────")

    if category == "budget":
        sub_totals = df.groupby('subcategory')['amount_usd'].sum()
        for sub, total in sub_totals.items():
            summary_lines.append(f"• **Total {sub.capitalize()}**: {fmt_usd(total)}")

        savings_df = df[df['subcategory'] == 'savings']
        if not savings_df.empty:
            summary_lines.append("\n💰 **Savings Breakdown (USD):**")
            actor_savings = savings_df.groupby('actor')['amount_usd'].sum()
            total_savings = savings_df['amount_usd'].sum()
            for actor, val in actor_savings.items():
                pct = (val / total_savings) * 100 if total_savings else 0
                summary_lines.append(f"  - 👤 **{actor}**: {fmt_usd(val)} ({pct:.1f}%)")
            goal_usd = convert_to_usd(1000, "MXN")
            pct_goal = (total_savings / goal_usd) * 100
            bar_len = 12
            filled = int(round((pct_goal / 100) * bar_len))
            filled = min(filled, bar_len)
            bar = "█" * filled + "░" * (bar_len - filled)
            summary_lines.append(f"🎯 **Goal Progress** (~{fmt_usd(goal_usd)}): `[{bar}]` **{pct_goal:.1f}%**")

        expenses_df = df[df['subcategory'] == 'expenses']
        if not expenses_df.empty:
            summary_lines.append("\n🛒 **Expenses / Spending Balance (USD):**")
            spent_by = expenses_df.groupby('actor')['amount_usd'].sum()
            summary_lines.append("**Total Out-of-Pocket Spending:**")
            for actor in VALID_ACTORS[:2]:
                val = spent_by.get(actor, 0.0)
                summary_lines.append(f"  - 👤 **{actor}**: {fmt_usd(val)}")

            def get_subtotal(actor, beneficiary):
                filt = expenses_df[(expenses_df['actor'] == actor) & (expenses_df['beneficiary'] == beneficiary)]
                return filt['amount_usd'].sum()

            g_for_k = get_subtotal("Gerardo", "Kristina")
            g_for_both = get_subtotal("Gerardo", "Both")
            k_for_g = get_subtotal("Kristina", "Gerardo")
            k_for_both = get_subtotal("Kristina", "Both")

            g_owes = k_for_g + (k_for_both / 2.0)
            k_owes = g_for_k + (g_for_both / 2.0)

            summary_lines.append("\n**Who benefits from the spendings:**")
            summary_lines.append(f"  - 👤 **Gerardo**'s benefit from Kristina: {fmt_usd(k_for_g)}")
            summary_lines.append(f"  - 👤 **Kristina**'s benefit from Gerardo: {fmt_usd(g_for_k)}")
            if g_for_both > 0 or k_for_both > 0:
                summary_lines.append(f"  - 👥 **Shared (Both):** paid by Gerardo {fmt_usd(g_for_both)} | paid by Kristina {fmt_usd(k_for_both)}")
                summary_lines.append(f"    ↳ 50/50 split → Gerardo's share {fmt_usd(g_for_both/2)} | Kristina's share {fmt_usd(k_for_both/2)}")

            summary_lines.append("\n⚖️ **Settlement Balance (USD):**")
            if abs(g_owes - k_owes) < 0.01:
                summary_lines.append("  - 🎉 **You are completely even!**")
            elif k_owes > g_owes:
                summary_lines.append(f"  - 🟢 **Kristina owes Gerardo:** {fmt_usd(k_owes - g_owes)}")
            else:
                summary_lines.append(f"  - 🔴 **Gerardo owes Kristina:** {fmt_usd(g_owes - k_owes)}")

    elif category == "houselife":
        sub_totals = df.groupby(['subcategory', 'actor']).size().unstack(fill_value=0)
        summary_lines.append("🧹 **Chore Leaderboard:**")
        for sub in sub_totals.index:
            summary_lines.append(f"\n• **{sub.capitalize()}**:")
            for actor in sub_totals.columns:
                count = sub_totals.loc[sub, actor]
                emoji = "🧼" if "dish" in sub.lower() else "🧹"
                summary_lines.append(f"  - 👤 **{actor}**: {emoji * count} ({count} times)")

    else:
        sub_totals = df.groupby('subcategory')['amount_usd'].sum()
        summary_lines.append("📈 **Subcategories (USD):**")
        for sub, total in sub_totals.items():
            summary_lines.append(f"• **{sub.capitalize()}**: {fmt_usd(total)}")
        summary_lines.append("\n👤 **Contributions (USD):**")
        actor_totals = df.groupby('actor')['amount_usd'].sum()
        for actor, total in actor_totals.items():
            summary_lines.append(f"• **{actor}**: {fmt_usd(total)}")

    summary_lines.append("\n📝 **Recent Activity (Last 5 items):**")
    for entry in entries[-5:]:
        orig = fmt_orig(entry)
        usd = entry.get("amount_usd", 0)
        ben_str = f" for {entry.get('beneficiary', 'Both')}" if 'beneficiary' in entry else ""
        summary_lines.append(f"• `{entry['date']}` **{entry['actor']}**{ben_str}: {entry['subcategory'].capitalize()} ({orig} ≈ {fmt_usd(usd)}) - *{entry['notes']}*")

    return "\n".join(summary_lines)

def generate_visual_report(category):
    data = load_data(category)
    entries = data.get("entries", [])
    if not entries:
        return False, "No data to plot"
    df = pd.DataFrame(entries)
    if 'beneficiary' not in df.columns:
        df['beneficiary'] = 'Both'
    if 'amount_usd' not in df.columns:
        df['amount_usd'] = df.get('value', 0)
    os.makedirs(REPORTS_DIR, exist_ok=True)
    plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')

    if category == "budget":
        expenses_df = df[df['subcategory'] == 'expenses']
        if expenses_df.empty:
            return False, "No expenses data to plot"
        spent = expenses_df.groupby('actor')['amount_usd'].sum()
        benefited = expenses_df.groupby('beneficiary')['amount_usd'].sum()
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6))
        spent.plot(kind='bar', color=['#3498db', '#e74c3c'], ax=ax1)
        ax1.set_title('Total Out-of-Pocket Expenses (USD)', fontsize=12, fontweight='bold')
        ax1.set_ylabel('Amount (USD)', fontsize=10)
        ax1.set_xlabel('Spender', fontsize=10)
        ax1.set_xticklabels(ax1.get_xticklabels(), rotation=0)
        benefited.plot(kind='bar', color=['#2ecc71', '#9b59b6', '#f1c40f'], ax=ax2)
        ax2.set_title('Expenses by Beneficiary (USD)', fontsize=12, fontweight='bold')
        ax2.set_ylabel('Benefit Amount (USD)', fontsize=10)
        ax2.set_xlabel('Beneficiary', fontsize=10)
        ax2.set_xticklabels(ax2.get_xticklabels(), rotation=0)
        plt.suptitle('Altata House — Budget Expense Analysis (USD)', fontsize=14, fontweight='bold')
        plt.tight_layout()
        plot_path = os.path.join(REPORTS_DIR, 'budget_expenses.png')
        plt.savefig(plot_path, dpi=300)
        plt.close()
        return True, plot_path
    elif category == "houselife":
        plt.figure(figsize=(10, 6))
        chore_counts = df.groupby(['subcategory', 'actor']).size().unstack(fill_value=0)
        chore_counts.plot(kind='bar', stacked=True, color=['#3498db', '#e74c3c'], figsize=(10, 6))
        plt.title('Houselife Chore Leaderboard', fontsize=14, fontweight='bold', pad=15)
        plt.xlabel('Chore Type', fontsize=12)
        plt.ylabel('Count', fontsize=12)
        plt.xticks(rotation=45)
        plt.legend(frameon=True, facecolor='white')
        plt.tight_layout()
        plot_path = os.path.join(REPORTS_DIR, 'houselife_chores.png')
        plt.savefig(plot_path, dpi=300)
        plt.close()
        return True, plot_path
    return False, "Visual report not implemented for this category yet"

def print_help():
    print("Usage:")
    print("  tracker.py add <category> <subcategory> <actor> <beneficiary> <amount> <currency> <notes> [date]")
    print("    currency: MXN | JPY | USD")
    print("  tracker.py summary <category>")
    print("  tracker.py validate")
    print("  tracker.py plot <category>")
    print("  tracker.py rates")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print_help()
        sys.exit(1)
    cmd = sys.argv[1]

    if cmd == "add":
        if len(sys.argv) < 9:
            print("Error: Missing arguments for add.")
            print("Usage: tracker.py add <category> <subcategory> <actor> <beneficiary> <amount> <currency> <notes> [date]")
            sys.exit(1)
        cat, sub, act, ben, amount, cur, notes = sys.argv[2:9]
        dt = sys.argv[9] if len(sys.argv) > 9 else None
        success, res = add_entry(cat, sub, act, ben, amount, cur, notes, dt)
        if success:
            print(f"SUCCESS: Added entry - {res}")
        else:
            print(f"ERROR: {res}")
            sys.exit(1)
    elif cmd == "summary":
        if len(sys.argv) < 3:
            print("Error: Missing category.")
            sys.exit(1)
        print(get_text_summary(sys.argv[2]))
    elif cmd == "validate":
        print(yaml.safe_dump(validate_all_data(), default_flow_style=False))
    elif cmd == "plot":
        if len(sys.argv) < 3:
            print("Error: Missing category.")
            sys.exit(1)
        success, res = generate_visual_report(sys.argv[2])
        if success:
            print(f"SUCCESS: Visual report saved to: {res}")
        else:
            print(f"ERROR: {res}")
            sys.exit(1)
    elif cmd == "rates":
        r = get_rates()
        print(f"Live rates (units per 1 USD): {r}")
    else:
        print(f"Unknown command: '{cmd}'")
        sys.exit(1)
