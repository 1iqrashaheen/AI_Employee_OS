"""Checked calculations: small data set whose answers are known by hand."""
import pandas as pd
import reports as R

sales = pd.DataFrame({"date": pd.to_datetime(["2026-01-05", "2026-01-20", "2026-02-10"]),
                      "customer": ["A", "B", "A"], "amount": [1000, 2000, 3000],
                      "status": ["paid", "unpaid", "paid"]})
expenses = pd.DataFrame({"date": pd.to_datetime(["2026-01-01", "2026-02-01"]),
                         "category": ["Rent", "Rent"], "amount": [500, 700]})
for d in (sales, expenses):
    d["month"] = d["date"].dt.to_period("M").astype(str)


def test_summary():
    s = R.summary(sales, expenses)
    assert s["revenue"] == 6000 and s["expenses"] == 1200
    assert s["profit"] == 4800 and s["unpaid"] == 2000 and s["margin_pct"] == 80.0


def test_monthly():
    m = R.monthly(sales, expenses).set_index("month")
    assert m.loc["2026-01", "revenue"] == 3000 and m.loc["2026-01", "profit"] == 2500
    assert m.loc["2026-02", "revenue"] == 3000 and m.loc["2026-02", "profit"] == 2300


def test_top_customer():
    t = R.top_customers(sales)
    assert t.iloc[0]["customer"] == "A" and t.iloc[0]["total"] == 4000


def test_forecast_needs_enough_data():
    assert R.forecast(R.monthly(sales, expenses))["ok"] is False  # only 2 months of data


def test_forecast_linear():
    df = pd.DataFrame({"month": [f"2026-0{i}" for i in range(1, 7)], "revenue": [100, 200, 300, 400, 500, 600]})
    f = R.forecast(df)
    assert f["ok"] and [r["revenue"] for r in f["forecast"]] == [700, 800, 900]
