"""Short explanations. Uses Claude if ANTHROPIC_API_KEY is set, otherwise rule-based."""
import json
import os
import urllib.request


def _rule_based(kind, data):
    if kind == "summary":
        s = data
        word = "profit" if s["profit"] >= 0 else "loss"
        return (f"Total revenue was Rs {s['revenue']:,} and expenses were Rs {s['expenses']:,}, "
                f"giving a {word} of Rs {abs(s['profit']):,} ({s['margin_pct']}% margin). "
                f"Rs {s['unpaid']:,} is still unpaid, so collecting it should be a priority.")
    if kind == "monthly":
        best = max(data, key=lambda r: r["profit"])
        worst = min(data, key=lambda r: r["profit"])
        first, last = data[0]["revenue"], data[-1]["revenue"]
        ch = (last - first) / first * 100 if first else 0
        return (f"The highest profit was in {best['month']} (Rs {int(best['profit']):,}) and the lowest "
                f"in {worst['month']} (Rs {int(worst['profit']):,}). From the first month to the last, "
                f"revenue changed by {ch:+.1f}%.")
    if kind == "expenses":
        total = sum(r["total"] for r in data)
        top = data[0]
        return (f"The largest expense is {top['category']} at Rs {int(top['total']):,} "
                f"({top['total'] / total * 100:.0f}% of total expenses).")
    if kind == "customers":
        top = data[0]
        total = sum(r["total"] for r in data)
        return (f"The top customer is {top['customer']} (Rs {int(top['total']):,}). "
                f"The top {len(data)} customers together bought Rs {int(total):,}.")
    if kind == "forecast":
        if not data.get("ok"):
            return data["message"]
        f = data["forecast"]
        d = "growing" if data["monthly_change"] >= 0 else "falling"
        return (f"Revenue has been {d} by about Rs {abs(data['monthly_change']):,} per month. "
                f"The estimate for {f[0]['month']} is Rs {f[0]['revenue']:,}. "
                f"This is only an estimate, not a guarantee.")
    return ""


def explain(kind, data):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return {"text": _rule_based(kind, data), "source": "rule-based"}
    try:
        prompt = ("You are a business analyst. In 2-3 simple sentences, explain these "
                  f"{kind} numbers for a small business owner. Use plain language, no markdown.\n"
                  + json.dumps(data, default=str))
        body = json.dumps({"model": "claude-sonnet-4-6", "max_tokens": 300,
                           "messages": [{"role": "user", "content": prompt}]}).encode()
        req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, headers={
            "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
        with urllib.request.urlopen(req, timeout=20) as r:
            out = json.load(r)
        return {"text": out["content"][0]["text"], "source": "claude"}
    except Exception:
        return {"text": _rule_based(kind, data), "source": "rule-based (API failed)"}
