"""Chhoti explanation. ANTHROPIC_API_KEY ho to Claude se, warna rule-based."""
import json
import os
import urllib.request


def _rule_based(kind, data):
    if kind == "summary":
        s = data
        word = "profit" if s["profit"] >= 0 else "loss"
        return (f"Total revenue Rs {s['revenue']:,} aur expenses Rs {s['expenses']:,} rahe, "
                f"yani Rs {abs(s['profit']):,} ka {word} ({s['margin_pct']}% margin). "
                f"Rs {s['unpaid']:,} abhi unpaid hai, us ki recovery par focus karein.")
    if kind == "monthly":
        best = max(data, key=lambda r: r["profit"])
        worst = min(data, key=lambda r: r["profit"])
        first, last = data[0]["revenue"], data[-1]["revenue"]
        ch = (last - first) / first * 100 if first else 0
        return (f"Sab se zyada profit {best['month']} mein (Rs {int(best['profit']):,}) aur sab se kam "
                f"{worst['month']} mein (Rs {int(worst['profit']):,}) hua. Pehle mahine se aakhri mahine tak "
                f"revenue {ch:+.1f}% badla.")
    if kind == "expenses":
        total = sum(r["total"] for r in data)
        top = data[0]
        return (f"Sab se bara kharcha {top['category']} hai: Rs {int(top['total']):,} "
                f"(kul expenses ka {top['total'] / total * 100:.0f}%).")
    if kind == "customers":
        top = data[0]
        total = sum(r["total"] for r in data)
        return (f"Top customer {top['customer']} hai (Rs {int(top['total']):,}). "
                f"Top {len(data)} customers ne mil kar Rs {int(total):,} ki sales ki.")
    if kind == "forecast":
        if not data.get("ok"):
            return data["message"]
        f = data["forecast"]
        d = "barh" if data["monthly_change"] >= 0 else "kam ho"
        return (f"Trend ke hisaab se revenue har mahine taqreeban Rs {abs(data['monthly_change']):,} {d} raha hai. "
                f"{f[0]['month']} ka andaza Rs {f[0]['revenue']:,} hai. Ye sirf andaza hai, pakka nahi.")
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
