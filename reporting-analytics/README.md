# AI Reporting and Analytics (Module 9, AI Employee OS)

Sales, revenue, expense and customer reports with charts, short AI explanations and a simple revenue forecast.

## Setup
```
python -m pip install -r requirements.txt
python generate_data.py
python app.py
```
Then open http://127.0.0.1:5000 in your browser.

`generate_data.py` creates the sample data (12 months, 8 customers) in the `data/` folder.

## Optional: AI explanations with Claude
Without an API key, the app uses a rule-based explanation. To use Claude, set the key before running `app.py`:
```
$env:ANTHROPIC_API_KEY="your_key_here"   (PowerShell)
set ANTHROPIC_API_KEY=your_key_here      (CMD)
```
The page shows "Source: claude" or "Source: rule-based" under each explanation.

## Run the tests (checked calculations)
```
python -m pytest -v
```
The tests check totals, monthly profit, top customers and the forecast against values calculated by hand.

## Files
- `generate_data.py`: creates the sample data
- `reports.py`: all calculations and the forecast
- `ai_explain.py`: short AI explanations (Claude API or rule-based)
- `app.py`: Flask server with the `/api/report` endpoint
- `templates/index.html`: report page and charts (Chart.js)
- `test_reports.py`: tests for the calculations
- `screenshots/`: testing evidence

## Reports included
- Summary: revenue, expenses, profit, margin, unpaid amount
- Monthly revenue, expenses and profit chart
- Expenses by category chart
- Top customers table
- 3-month revenue forecast

## Limitations and future work
- The module currently uses sample CSV data. For final integration, `load()` in `reports.py` will be replaced with calls to the shared backend API.
- The forecast is a simple linear trend with no seasonality, and only runs when there are at least 6 months of data.
- Reports are not yet filtered per user or per date range.
