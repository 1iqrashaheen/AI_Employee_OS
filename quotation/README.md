# Quotation Generator

Module 10 of AI Employee OS. Owner: Arayash Noor.

## What it does

A form where the user enters company details, customer details, items,
discounts and tax. It shows the totals live and downloads a PDF quotation.

## Files

| File | Purpose |
|---|---|
| `quotation.py` | Calculations and PDF generation. No web code. |
| `api.py` | FastAPI endpoints and the page route. |
| `quotation_form.html` | The quotation form (plain HTML and JavaScript). |
| `sample_quotation.pdf` | Example of the PDF output. |

## Install and run

From the project's main folder, with the virtual environment active:

```
pip install fastapi uvicorn reportlab
python quotation/quotation.py
uvicorn quotation.api:app --reload --port 8002
```

The first command installs the libraries. The second runs the checked
examples and should print `All checks passed.` The third starts the server.
Open http://127.0.0.1:8002 in a browser.

## API

| Endpoint | Purpose |
|---|---|
| `POST /api/quotations/calculate` | Returns each line amount and the totals as JSON. |
| `POST /api/quotations/pdf` | Returns the quotation as a PDF file. |

To add the module to the main backend:

```python
from quotation.api import router
app.include_router(router)
```

## Request format

All percentages are decimals: `0.10` means 10%, `0.17` means 17%. Values above
1 are rejected with a clear message.

```json
{
  "quotation_number": "Q-2026-001",
  "currency": "USD",
  "company": {"name": "Example Company", "address": "12 Main Street", "email": "sales@example.com", "phone": "+92 300 0000000"},
  "customer": {"name": "John Smith", "company": "Smith Traders", "address": "45 Market Road", "email": "john@example.com"},
  "items": [
    {"description": "Laptop", "quantity": 25, "unit_price": 800, "discount": 0.05},
    {"description": "Mouse", "quantity": 25, "unit_price": 10}
  ],
  "discount": 0.02,
  "tax_rate": 0.17,
  "notes": "Optional notes",
  "terms": "Optional terms"
}
```

Optional fields: `date` (YYYY-MM-DD, default today), `valid_days` (default 30),
`footer`.

## Calculation order

```
line amount     = quantity x unit price x (1 - item discount)
subtotal        = sum of line amounts
discount amount = subtotal x overall discount
taxable amount  = subtotal - discount amount
tax amount      = taxable amount x tax rate
total           = taxable amount + tax amount
```

Money is calculated with exact decimals and rounded half-up to 2 places.

## Checked example

25 laptops at 800 with a 5% line discount (19,000.00) and 25 mice at 10
(250.00) give a subtotal of 19,250.00. A 2% overall discount (385.00) leaves
18,865.00. Tax at 17% is 3,207.05, so the total is 22,072.05.

## Limits

- Quotations are not saved to a database yet. Saving, customer lookup and
  email delivery depend on the shared backend and the CRM and email modules.
- Amounts show a currency code (for example USD) instead of a symbol.
