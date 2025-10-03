"""
Personal Expense Tracker - single-file Python app (CLI + GUI with Tkinter) using SQLite
Now with Budget Limit & Warnings

Usage:
  - Run GUI:   python expense_tracker.py --gui
  - Run CLI:   python expense_tracker.py --cli
"""

import argparse
import sqlite3
import datetime
import os
import csv

# GUI imports
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog

# ----------------------------
# Configuration / DB helpers
# ----------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "expenses.db")

DATE_FMT = "%Y-%m-%d"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Expenses table
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            amount REAL NOT NULL,
            date TEXT NOT NULL,
            note TEXT
        );
        """
    )
    # Settings table (for budget)
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        """
    )
    conn.commit()
    conn.close()


def add_expense_db(category: str, amount: float, date_str: str, note: str = ""):
    # Validate/normalize date
    if not date_str:
        date_str = datetime.date.today().strftime(DATE_FMT)
    else:
        try:
            d = datetime.datetime.strptime(date_str, DATE_FMT).date()
            date_str = d.strftime(DATE_FMT)
        except Exception:
            raise ValueError("Date must be in YYYY-MM-DD format")

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO expenses (category, amount, date, note) VALUES (?, ?, ?, ?)",
        (category, float(amount), date_str, note),
    )
    conn.commit()
    conn.close()

    # After adding, check budget
    budget = get_budget_limit()
    if budget is not None:
        total = get_monthly_total()
        if total > budget:
            return f"⚠️ Warning: Total monthly expenses ₹{total} exceeded your budget ₹{budget}!"
    return None


def get_summary_range(start_date: str, end_date: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT category, SUM(amount) as total FROM expenses WHERE date >= ? AND date <= ? GROUP BY category ORDER BY total DESC",
        (start_date, end_date),
    )
    rows = c.fetchall()
    conn.close()
    return rows


def get_summary_period(period: str):
    today = datetime.date.today()
    if period == "weekly":
        start = today - datetime.timedelta(days=6)  # last 7 days inclusive
        end = today
    elif period == "monthly":
        start = today.replace(day=1)
        end = today
    else:
        raise ValueError("Unknown period")

    return get_summary_range(start.strftime(DATE_FMT), end.strftime(DATE_FMT))


def get_entries_range(start_date: str = None, end_date: str = None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if start_date and end_date:
        c.execute(
            "SELECT id, category, amount, date, note FROM expenses WHERE date >= ? AND date <= ? ORDER BY date DESC, id DESC",
            (start_date, end_date),
        )
    else:
        c.execute("SELECT id, category, amount, date, note FROM expenses ORDER BY date DESC, id DESC")
    rows = c.fetchall()
    conn.close()
    return rows


def delete_entry_db(entry_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM expenses WHERE id = ?", (entry_id,))
    conn.commit()
    conn.close()


def export_csv(filename: str, start_date: str = None, end_date: str = None):
    rows = get_entries_range(start_date, end_date) if start_date and end_date else get_entries_range()
    with open(filename, "w", newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["id", "category", "amount", "date", "note"])
        for r in rows:
            writer.writerow(r)


# ----------------------------
# Budget helpers
# ----------------------------

def set_budget_limit(amount: float):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('budget', ?)", (str(amount),))
    conn.commit()
    conn.close()


def get_budget_limit():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key='budget'")
    row = c.fetchone()
    conn.close()
    if row:
        return float(row[0])
    return None


def get_monthly_total():
    today = datetime.date.today()
    start = today.replace(day=1)
    end = today
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT SUM(amount) FROM expenses WHERE date >= ? AND date <= ?", (start.strftime(DATE_FMT), end.strftime(DATE_FMT)))
    row = c.fetchone()
    conn.close()
    return row[0] if row and row[0] else 0.0


# ----------------------------
# CLI mode
# ----------------------------

def cli_add():
    try:
        cat = input("Category (Food, Rent, Travel, ...): ").strip()
        amt = input("Amount: ").strip()
        note = input("Note (optional): ").strip()
        date = input("Date (YYYY-MM-DD, leave blank for today): ").strip()
        warning = add_expense_db(cat, float(amt), date, note)
        print("✅ Expense added.")
        if warning:
            print(warning)
    except Exception as e:
        print("Error adding expense:", e)


def cli_show_summary(period="monthly"):
    rows = get_summary_period(period)
    print(f"\n{period.capitalize()} summary ({datetime.date.today().strftime(DATE_FMT)}):")
    total = 0.0
    if not rows:
        print("No expenses found for this period.")
    for cat, s in rows:
        print(f"  {cat}: {s}")
        total += s
    print(f"  TOTAL: {total}")
    budget = get_budget_limit()
    if budget:
        print(f"  Budget Limit: {budget}")
        if total > budget:
            print(f"⚠️ WARNING: Expenses exceeded budget by {total - budget}\n")
    print()


def cli_set_budget():
    amt = input("Enter monthly budget (₹): ").strip()
    try:
        set_budget_limit(float(amt))
        print(f"✅ Budget set to ₹{amt}")
    except:
        print("Invalid input")


def cli_show_entries():
    rows = get_entries_range()
    if not rows:
        print("No entries yet.")
        return
    print("Recent entries:")
    for r in rows:
        print(r)


def cli_export():
    fn = input("Enter filename to save CSV (e.g. out.csv): ").strip()
    start = input("Start date (YYYY-MM-DD) or leave blank: ").strip()
    end = input("End date (YYYY-MM-DD) or leave blank: ").strip()
    try:
        if start and end:
            export_csv(fn, start, end)
        else:
            export_csv(fn)
        print("Exported to", fn)
    except Exception as e:
        print("Export failed:", e)


def run_cli():
    print("Simple Expense Tracker - CLI")
    while True:
        print("\n1. Add expense")
        print("2. Show weekly summary")
        print("3. Show monthly summary")
        print("4. Set budget")
        print("5. Show all entries")
        print("6. Export CSV")
        print("7. Exit")
        ch = input("Choice: ").strip()
        if ch == "1":
            cli_add()
        elif ch == "2":
            cli_show_summary("weekly")
        elif ch == "3":
            cli_show_summary("monthly")
        elif ch == "4":
            cli_set_budget()
        elif ch == "5":
            cli_show_entries()
        elif ch == "6":
            cli_export()
        elif ch == "7":
            break
        else:
            print("Invalid choice")


# ----------------------------
# GUI mode (Tkinter)
# ----------------------------

class ExpenseTrackerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Personal Expense Tracker")
        self.geometry("850x600")
        self.style = ttk.Style(self)
        self.default_categories = ["Food", "Rent", "Transport", "Bills", "Shopping", "Entertainment", "Other"]
        self.create_widgets()
        self.refresh_entries()

    def create_widgets(self):
        # Add expense frame
        frm_add = ttk.LabelFrame(self, text="Add Expense")
        frm_add.pack(fill="x", padx=10, pady=8)

        ttk.Label(frm_add, text="Category:").grid(row=0, column=0, padx=6, pady=6, sticky="w")
        self.entry_category = ttk.Combobox(frm_add, values=self.default_categories)
        self.entry_category.set(self.default_categories[0])
        self.entry_category.grid(row=0, column=1, padx=6, pady=6)

        ttk.Label(frm_add, text="Amount:").grid(row=0, column=2, padx=6, pady=6, sticky="w")
        self.entry_amount = ttk.Entry(frm_add)
        self.entry_amount.grid(row=0, column=3, padx=6, pady=6)

        ttk.Label(frm_add, text="Date (YYYY-MM-DD):").grid(row=1, column=0, padx=6, pady=6, sticky="w")
        self.entry_date = ttk.Entry(frm_add)
        self.entry_date.insert(0, datetime.date.today().strftime(DATE_FMT))
        self.entry_date.grid(row=1, column=1, padx=6, pady=6)

        ttk.Label(frm_add, text="Note:").grid(row=1, column=2, padx=6, pady=6, sticky="w")
        self.entry_note = ttk.Entry(frm_add)
        self.entry_note.grid(row=1, column=3, padx=6, pady=6)

        btn_add = ttk.Button(frm_add, text="Add Expense", command=self.add_expense_gui)
        btn_add.grid(row=2, column=0, columnspan=4, pady=8)

        # Controls frame
        frm_ctrl = ttk.Frame(self)
        frm_ctrl.pack(fill="x", padx=10, pady=4)

        btn_week = ttk.Button(frm_ctrl, text="Show Weekly Summary", command=lambda: self.show_summary_gui("weekly"))
        btn_week.pack(side="left", padx=6)

        btn_month = ttk.Button(frm_ctrl, text="Show Monthly Summary", command=lambda: self.show_summary_gui("monthly"))
        btn_month.pack(side="left", padx=6)

        btn_budget = ttk.Button(frm_ctrl, text="Set Budget", command=self.set_budget_gui)
        btn_budget.pack(side="left", padx=6)

        btn_export = ttk.Button(frm_ctrl, text="Export CSV", command=self.export_csv_gui)
        btn_export.pack(side="left", padx=6)

        btn_refresh = ttk.Button(frm_ctrl, text="Refresh Entries", command=self.refresh_entries)
        btn_refresh.pack(side="left", padx=6)

        btn_delete = ttk.Button(frm_ctrl, text="Delete Selected", command=self.delete_selected)
        btn_delete.pack(side="right", padx=6)

        # Entries treeview
        columns = ("id", "date", "category", "amount", "note")
        self.tree = ttk.Treeview(self, columns=columns, show="headings")
        for col in columns:
            self.tree.heading(col, text=col.title())
            if col == "amount":
                self.tree.column(col, width=100, anchor="e")
            elif col == "id":
                self.tree.column(col, width=50, anchor="center")
            else:
                self.tree.column(col, width=150)

        self.tree.pack(fill="both", expand=True, padx=10, pady=8)

    def add_expense_gui(self):
        cat = self.entry_category.get().strip()
        amt = self.entry_amount.get().strip()
        date = self.entry_date.get().strip()
        note = self.entry_note.get().strip()
        if not cat or not amt:
            messagebox.showerror("Error", "Please enter category and amount")
            return
        try:
            warning = add_expense_db(cat, float(amt), date, note)
            if warning:
                messagebox.showwarning("Budget Exceeded", warning)
            else:
                messagebox.showinfo("Added", "Expense added successfully")
            self.entry_amount.delete(0, tk.END)
            self.entry_note.delete(0, tk.END)
            self.entry_date.delete(0, tk.END)
            self.entry_date.insert(0, datetime.date.today().strftime(DATE_FMT))
            self.refresh_entries()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def refresh_entries(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        rows = get_entries_range()
        for r in rows:
            self.tree.insert("", tk.END, values=r)

    def show_summary_gui(self, period: str):
        rows = get_summary_period(period)
        win = tk.Toplevel(self)
        win.title(f"{period.capitalize()} Summary")
        win.geometry("400x300")
        cols = ("category", "total")
        tv = ttk.Treeview(win, columns=cols, show="headings")
        tv.heading("category", text="Category")
        tv.heading("total", text="Total")
        tv.pack(fill="both", expand=True, padx=8, pady=8)
        total_sum = 0.0
        for cat, s in rows:
            tv.insert("", tk.END, values=(cat, s))
            total_sum += s
        budget = get_budget_limit()
        lbl = ttk.Label(win, text=f"TOTAL: {total_sum}")
        lbl.pack(pady=6)
        if budget:
            lbl2 = ttk.Label(win, text=f"Budget Limit: {budget}")
            lbl2.pack()
            if total_sum > budget:
                lbl3 = ttk.Label(win, text=f"⚠️ Exceeded by {total_sum - budget}", foreground="red")
                lbl3.pack()

    def set_budget_gui(self):
        amt = simpledialog.askfloat("Set Budget", "Enter monthly budget (₹):")
        if amt:
            set_budget_limit(amt)
            messagebox.showinfo("Budget Set", f"Budget set to ₹{amt}")

    def export_csv_gui(self):
        fn = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        if not fn:
            return
        res = messagebox.askyesno("Date range?", "Export only a date range? (Yes to choose, No to export all)")
        try:
            if res:
                start = simpledialog.askstring("Start date", "Start date (YYYY-MM-DD):")
                end = simpledialog.askstring("End date", "End date (YYYY-MM-DD):")
                if not start or not end:
                    messagebox.showerror("Error", "Start and end date required")
                    return
                export_csv(fn, start, end)
            else:
                export_csv(fn)
            messagebox.showinfo("Exported", f"Saved to {fn}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def delete_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showerror("Error", "Select a row to delete")
            return
        answer = messagebox.askyesno("Confirm", "Delete selected entry?")
        if not answer:
            return
        item = sel[0]
        values = self.tree.item(item, "values")
        entry_id = int(values[0])
        delete_entry_db(entry_id)
        self.refresh_entries()
        messagebox.showinfo("Deleted", "Entry deleted")


# ----------------------------
# Entrypoint
# ----------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gui", action="store_true", help="Run the GUI")
    parser.add_argument("--cli", action="store_true", help="Run the CLI")
    args = parser.parse_args()

    init_db()

    if args.gui:
        app = ExpenseTrackerApp()
        app.mainloop()
    elif args.cli:
        run_cli()
    else:
        print("Specify --gui or --cli. Example: python expense_tracker.py --gui")


if __name__ == "__main__":
    main()
