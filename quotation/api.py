"""
api.py - Quotation API (AI Employee OS, module 10)

Endpoints:
  GET  /                              the quotation form page
  POST /api/quotations/calculate      returns line amounts and totals (JSON)
  POST /api/quotations/pdf            returns the quotation as a PDF file

All percentages are decimals: 0.10 means 10%.

Run from the project's main folder:
  uvicorn quotation.api:app --reload --port 8002
Then open http://127.0.0.1:8002

To plug into the main backend later:
  from quotation.api import router
  app.include_router(router)
"""

import os
import tempfile
from typing import List, Optional

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from .quotation import calculate_quotation, create_quotation_pdf

FORM_PAGE = os.path.join(os.path.dirname(__file__), "quotation_form.html")


class Company(BaseModel):
    name: str = "Company name"
    address: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None


class Customer(BaseModel):
    name: Optional[str] = None
    company: Optional[str] = None
    address: Optional[str] = None
    email: Optional[str] = None


class Item(BaseModel):
    description: str
    quantity: float
    unit_price: float
    discount: float = 0.0            # decimal: 0.05 = 5%


class QuotationRequest(BaseModel):
    quotation_number: str = "DRAFT"
    date: Optional[str] = None        # YYYY-MM-DD, default today
    valid_days: int = 30
    currency: str = "USD"
    company: Company = Field(default_factory=Company)
    customer: Customer = Field(default_factory=Customer)
    items: List[Item]
    discount: float = 0.0             # overall discount, decimal
    tax_rate: float = 0.0             # decimal: 0.17 = 17%
    notes: Optional[str] = None
    terms: Optional[str] = None


router = APIRouter(prefix="/api/quotations", tags=["quotations"])


@router.post("/calculate")
def calculate(req: QuotationRequest):
    try:
        return calculate_quotation(req.model_dump())
    except ValueError as err:
        raise HTTPException(status_code=422, detail=str(err))


@router.post("/pdf")
def pdf(req: QuotationRequest):
    data = req.model_dump()
    handle, path = tempfile.mkstemp(suffix=".pdf")
    os.close(handle)
    try:
        create_quotation_pdf(data, path)
        with open(path, "rb") as f:
            content = f.read()
    except ValueError as err:
        raise HTTPException(status_code=422, detail=str(err))
    finally:
        os.remove(path)
    filename = f"quotation_{req.quotation_number}.pdf".replace(" ", "_")
    return Response(content, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


app = FastAPI(title="Quotation Generator")
app.include_router(router)


@app.get("/", include_in_schema=False)
def form_page():
    return FileResponse(FORM_PAGE)
