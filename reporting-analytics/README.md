# AI Reporting and Analytics (Module 9, AI Employee OS)

Sales, revenue, expense and customer reports with charts, short AI explanations and a simple forecast.

## Setup
```
pip install -r requirements.txt
python generate_data.py     # sample data banata hai (data/ folder)
python app.py               # phir browser mein http://127.0.0.1:5000 kholo
```

## Optional: Claude se AI explanation
Bina key ke rule-based explanation aati hai. Claude use karne ke liye:
```
set ANTHROPIC_API_KEY=your_key_here      (Windows CMD)
$env:ANTHROPIC_API_KEY="your_key_here"   (PowerShell)
```

## Test (checked calculations)
```
python -m pytest -v
```

## Files
- `generate_data.py`: sample data (12 months, 8 customers)
- `reports.py`: saari calculations + forecast
- `ai_explain.py`: AI explanation (Claude API ya rule-based)
- `app.py`: Flask server, `/api/report`
- `templates/index.html`: report page + charts (Chart.js)
- `test_reports.py`: calculations ke tests

## Reports
Summary KPIs, monthly revenue/expenses/profit, expenses by category, top customers, 3-month revenue forecast.

## Limitations / future work
- Abhi CSV sample data use hota hai. Final integration mein `reports.load()` ko Hadeed ki backend API se replace karna hai.
- Forecast simple linear trend hai (seasonality nahi), aur sirf 6+ mahine ke data par chalta hai.
- Login/user-wise reports abhi nahi hain.
