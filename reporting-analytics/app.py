from flask import Flask, jsonify, render_template
import reports as R
from ai_explain import explain

app = Flask(__name__)


def _all():
    sales, expenses, customers = R.load()
    m = R.monthly(sales, expenses)
    return {
        "summary": R.summary(sales, expenses),
        "monthly": m.to_dict("records"),
        "expenses": R.expense_by_category(expenses).to_dict("records"),
        "customers": R.top_customers(sales).to_dict("records"),
        "new_customers": R.new_customers_per_month(customers).to_dict("records"),
        "forecast": R.forecast(m),
    }


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/report")
def report():
    d = _all()
    d["explanations"] = {k: explain(k, d[k]) for k in ("summary", "monthly", "expenses", "customers", "forecast")}
    return jsonify(d)


if __name__ == "__main__":
    app.run(debug=True)
