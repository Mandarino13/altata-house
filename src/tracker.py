#!/usr/bin/env python3
import os
import sys
import yaml
import csv
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

def add_entry(category, subcategory, actor, beneficiary, value, notes, date_str=None):
    if actor not in VALID_ACTORS:
        return False, f"Invalid actor: '{actor}'. Must be one of {VALID_ACTORS}"
    if beneficiary not in VALID_BENEFICIARIES:
        return False, f"Invalid beneficiary: '{beneficiary}'. Must be one of {VALID_BENEFICIARIES}"
    
    try:
        val = float(value)
    except ValueError:
        return False, f"Value must be a number, got '{value}'"
        
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")
    else:
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            return False, f"Date must be in YYYY-MM-DD format, got '{date_str}'"

    # Load existing data
    data = load_data(category)
    
    # Create entry
    entry = {
        "date": date_str,
        "actor": actor,
        "beneficiary": beneficiary,
        "subcategory": subcategory,
        "value": val,
        "notes": notes.strip()
    }
    
    data["entries"].append(entry)
    
    # Save YAML
    if save_data(category, data):
        # Trigger automatic CSV export
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
            writer.writerow(["Date", "Actor", "Beneficiary", "Subcategory", "Value", "Notes"])
            for entry in data.get("entries", []):
                writer.writerow([
                    entry.get("date"),
                    entry.get("actor"),
                    entry.get("beneficiary", "Both"), # Default to Both for legacy compatibility
                    entry.get("subcategory"),
                    entry.get("value"),
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
        
        for idx, entry in enumerate(entries):
            # Check fields
            for field in ["date", "actor", "subcategory", "value", "notes"]:
                if field not in entry:
                    errors.append(f"Entry {idx}: Missing field '{field}'")
            
            # Check actor
            actor = entry.get("actor")
            if actor and actor not in VALID_ACTORS:
                errors.append(f"Entry {idx}: Invalid actor '{actor}'")
                
            # Check beneficiary
            beneficiary = entry.get("beneficiary")
            if beneficiary and beneficiary not in VALID_BENEFICIARIES:
                errors.append(f"Entry {idx}: Invalid beneficiary '{beneficiary}'")
                
            # Check value type
            value = entry.get("value")
            if value is not None:
                try:
                    float(value)
                except ValueError:
                    errors.append(f"Entry {idx}: Non-numeric value '{value}'")
                    
            # Check date format
            date = entry.get("date")
            if date:
                try:
                    datetime.strptime(date, "%Y-%m-%d")
                except ValueError:
                    errors.append(f"Entry {idx}: Invalid date format '{date}' (expected YYYY-MM-DD)")
                    
        report[cat] = {
            "status": "valid" if not errors else "invalid",
            "entry_count": len(entries),
            "errors": errors
        }
    return report

def get_text_summary(category):
    data = load_data(category)
    entries = data.get("entries", [])
    
    if not entries:
        return f"No entries found in category '{category}'."
        
    df = pd.DataFrame(entries)
    # Ensure beneficiary column exists for safety
    if 'beneficiary' not in df.columns:
        df['beneficiary'] = 'Both'
    else:
        df['beneficiary'] = df['beneficiary'].fillna('Both')
        
    summary_lines = []
    summary_lines.append(f"📊 **Altata House — {category.upper()} SUMMARY**")
    summary_lines.append("────────────────────────")
    
    if category == "budget":
        # Total overall expenses vs savings
        sub_totals = df.groupby('subcategory')['value'].sum()
        for sub, total in sub_totals.items():
            summary_lines.append(f"• **Total {sub.capitalize()}**: `${total:,.2f}`")
            
        # Savings progress
        savings_df = df[df['subcategory'] == 'savings']
        if not savings_df.empty:
            summary_lines.append("\n💰 **Savings Breakdown:**")
            actor_savings = savings_df.groupby('actor')['value'].sum()
            total_savings = savings_df['value'].sum()
            for actor, val in actor_savings.items():
                pct = (val / total_savings) * 100 if total_savings else 0
                summary_lines.append(f"  - 👤 **{actor}**: `${val:,.2f}` ({pct:.1f}%)")
            
            goal = 1000.0
            pct_goal = (total_savings / goal) * 100
            bar_len = 12
            filled = int(round((pct_goal / 100) * bar_len))
            filled = min(filled, bar_len)
            bar = "█" * filled + "░" * (bar_len - filled)
            summary_lines.append(f"🎯 **Goal Progress** (${goal:,.2f}): `[{bar}]` **{pct_goal:.1f}%**")

        # Expense/spending balance (Splitwise logic)
        expenses_df = df[df['subcategory'] == 'expenses']
        if not expenses_df.empty:
            summary_lines.append("\n🛒 **Expenses / Spending Balance:**")
            
            # Total spending by actor
            spent_by = expenses_df.groupby('actor')['value'].sum()
            summary_lines.append("**Total Out-of-Pocket Spending:**")
            for actor in VALID_ACTORS[:2]:
                val = spent_by.get(actor, 0.0)
                summary_lines.append(f"  - 👤 **{actor}**: `${val:,.2f}`")
                
            # Net Balance Calculation
            # Gerardo owes Kristina: (Kristina's spend for Gerardo) + (Kristina's spend for Both)/2
            # Kristina owes Gerardo: (Gerardo's spend for Kristina) + (Gerardo's spend for Both)/2
            
            # Helper function to get totals
            def get_subtotal(actor, beneficiary):
                filt = expenses_df[(expenses_df['actor'] == actor) & (expenses_df['beneficiary'] == beneficiary)]
                return filt['value'].sum()
                
            g_for_k = get_subtotal("Gerardo", "Kristina")
            g_for_both = get_subtotal("Gerardo", "Both")
            
            k_for_g = get_subtotal("Kristina", "Gerardo")
            k_for_both = get_subtotal("Kristina", "Both")
            
            g_owes = k_for_g + (k_for_both / 2.0)
            k_owes = g_for_k + (g_for_both / 2.0)
            
            summary_lines.append("\n**Who benefits from the spendings:**")
            summary_lines.append(f"  - 👤 **Gerardo**'s benefit from Kristina: `${k_for_g:,.2f}`")
            summary_lines.append(f"  - 👤 **Kristina**'s benefit from Gerardo: `${g_for_k:,.2f}`")
            summary_lines.append(f"  - 👥 Shared spendings (Both): Gerardo `${g_for_both:,.2f}` | Kristina `${k_for_both:,.2f}`")
            
            summary_lines.append("\n⚖️ **Settlement Balance:**")
            if g_owes == k_owes:
                summary_lines.append("  - 🎉 **You are completely even!**")
            elif k_owes > g_owes:
                diff = k_owes - g_owes
                summary_lines.append(f"  - 🟢 **Kristina owes Gerardo:** `${diff:,.2f}`")
            else:
                diff = g_owes - k_owes
                summary_lines.append(f"  - 🔴 **Gerardo owes Kristina:** `${diff:,.2f}`")

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
        sub_totals = df.groupby('subcategory')['value'].sum()
        summary_lines.append("📈 **Subcategories:**")
        for sub, total in sub_totals.items():
            summary_lines.append(f"• **{sub.capitalize()}**: {total}")
            
        summary_lines.append("\n👤 **Contributions:**")
        actor_totals = df.groupby('actor')['value'].sum()
        for actor, total in actor_totals.items():
            summary_lines.append(f"• **{actor}**: {total}")
            
    summary_lines.append("\n📝 **Recent Activity (Last 5 items):**")
    for entry in entries[-5:]:
        sub_val = f" (${entry['value']:,.2f})" if entry['value'] > 0 else ""
        ben_str = f" for {entry.get('beneficiary', 'Both')}" if 'beneficiary' in entry else ""
        summary_lines.append(f"• `{entry['date']}` **{entry['actor']}**{ben_str}: {entry['subcategory'].capitalize()}{sub_val} - *{entry['notes']}*")
        
    return "\n".join(summary_lines)

def generate_visual_report(category):
    data = load_data(category)
    entries = data.get("entries", [])
    if not entries:
        return False, "No data to plot"
        
    df = pd.DataFrame(entries)
    if 'beneficiary' not in df.columns:
        df['beneficiary'] = 'Both'
        
    os.makedirs(REPORTS_DIR, exist_ok=True)
    plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
    
    if category == "budget":
        # Draw a bar chart comparing expenses and beneficiary split
        expenses_df = df[df['subcategory'] == 'expenses']
        if expenses_df.empty:
            return False, "No expenses data to plot"
            
        # Group by actor and beneficiary
        plt.figure(figsize=(10, 6))
        
        # 1. Plot Out-of-pocket spending
        spent = expenses_df.groupby('actor')['value'].sum()
        
        # 2. Plot who the spending was for
        benefited = expenses_df.groupby('beneficiary')['value'].sum()
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6))
        
        # Spent by chart
        spent.plot(kind='bar', color=['#3498db', '#e74c3c'], ax=ax1)
        ax1.set_title('Total Out-of-Pocket Expenses', fontsize=12, fontweight='bold')
        ax1.set_ylabel('Spent Amount ($)', fontsize=10)
        ax1.set_xlabel('Spender', fontsize=10)
        ax1.set_xticklabels(ax1.get_xticklabels(), rotation=0)
        
        # Benefited chart
        benefited.plot(kind='bar', color=['#2ecc71', '#9b59b6', '#f1c40f'], ax=ax2)
        ax2.set_title('Expenses by Beneficiary', fontsize=12, fontweight='bold')
        ax2.set_ylabel('Benefit Amount ($)', fontsize=10)
        ax2.set_xlabel('Beneficiary', fontsize=10)
        ax2.set_xticklabels(ax2.get_xticklabels(), rotation=0)
        
        plt.suptitle('Altata House — Budget Expense Analysis', fontsize=14, fontweight='bold')
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

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  tracker.py add <category> <subcategory> <actor> <beneficiary> <value> <notes> [date]")
        print("  tracker.py summary <category>")
        print("  tracker.py validate")
        print("  tracker.py plot <category>")
        sys.exit(1)
        
    cmd = sys.argv[1]
    
    if cmd == "add":
        if len(sys.argv) < 8:
            print("Error: Missing arguments for add.")
            print("Usage: tracker.py add <category> <subcategory> <actor> <beneficiary> <value> <notes> [date]")
            sys.exit(1)
        cat, sub, act, ben, val, notes = sys.argv[2:8]
        dt = sys.argv[8] if len(sys.argv) > 8 else None
        
        success, res = add_entry(cat, sub, act, ben, val, notes, dt)
        if success:
            print(f"SUCCESS: Added entry - {res}")
        else:
            print(f"ERROR: {res}")
            sys.exit(1)
            
    elif cmd == "summary":
        if len(sys.argv) < 3:
            print("Error: Missing category.")
            sys.exit(1)
        cat = sys.argv[2]
        print(get_text_summary(cat))
        
    elif cmd == "validate":
        report = validate_all_data()
        print(yaml.safe_dump(report, default_flow_style=False))
        
    elif cmd == "plot":
        if len(sys.argv) < 3:
            print("Error: Missing category.")
            sys.exit(1)
        cat = sys.argv[2]
        success, res = generate_visual_report(cat)
        if success:
            print(f"SUCCESS: Visual report saved to: {res}")
        else:
            print(f"ERROR: {res}")
            sys.exit(1)
            
    else:
        print(f"Unknown command: '{cmd}'")
        sys.exit(1)
