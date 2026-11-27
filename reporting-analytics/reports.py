"""All calculations live here (separate from Flask so they can be tested)."""
import numpy as np
import pandas as pd

MIN_MONTHS_FOR_FORECAST = 6


def load(folder="data"):
    sales = pd.read_csv(f"{folder}/sales.csv", parse_dates=["date"])
    expenses = pd.read_csv(f"{folder}/expenses.csv", parse_dates=["date"])
    customers = pd.read_csv(f"{folder}/customers.csv", parse_dates=["created_at"])
    for df in (sales, expenses):
        df["month"] = df["date"].dt.to_period("M").astype(str)
    customers["month"] = customers["created_at"].dt.to_period("M").astype(str)
    return sales, expenses, customers


def monthly(sales, expenses):
    rev = sales.groupby("month")["amount"].sum().rename("revenue")
    exp = expenses.groupby("month")["amount"].sum().rename("expenses")
    df = pd.concat([rev, exp], axis=1).fillna(0).sort_index()
    df["profit"] = df["revenue"] - df["expenses"]
    return df.reset_index()


def summary(sales, expenses):
    revenue = int(sales["amount"].sum())
    total_exp = int(expenses["amount"].sum())
    unpaid = int(sales.loc[sales["status"] == "unpaid", "amount"].sum())
    return {"revenue": revenue, "expenses": total_exp, "profit": revenue - total_exp,
            "unpaid": unpaid, "invoices": int(len(sales)),
            "margin_pct": round((revenue - total_exp) / revenue * 100, 1) if revenue else 0}


def expense_by_category(expenses):
    g = expenses.groupby("category")["amount"].sum().sort_values(ascending=False)
    return g.reset_index().rename(columns={"amount": "total"})


def top_customers(sales, n=5):
    g = sales.groupby("customer")["amount"].agg(total="sum", invoices="count")
    return g.sort_values("total", ascending=False).head(n).reset_index()


def new_customers_per_month(customers):
    return customers.groupby("month").size().rename("new_customers").reset_index()


def forecast(monthly_df, steps=3):
    """Simple linear trend. Only runs when there are 6+ months of data."""
    n = len(monthly_df)
    if n < MIN_MONTHS_FOR_FORECAST:
        return {"ok": False,
                "message": f"A forecast needs at least {MIN_MONTHS_FOR_FORECAST} months of data, but only {n} are available."}
    y = monthly_df["revenue"].values
    x = np.arange(n)
    slope, intercept = np.polyfit(x, y, 1)
    last = pd.Period(monthly_df["month"].iloc[-1], freq="M")
    future = [{"month": str(last + i), "revenue": max(0, round(float(slope * (n - 1 + i) + intercept)))}
              for i in range(1, steps + 1)]
    return {"ok": True, "method": "Linear trend (least squares)",
            "monthly_change": round(float(slope)), "forecast": future}
