from typing import List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, conint, confloat

from quote_service import generate_quote
app = FastAPI(title="Cargo Quote API", version="1.0.0")


class Dimensions(BaseModel):
    length: confloat(ge=0) = 0
    width: confloat(ge=0) = 0
    height: confloat(ge=0) = 0


class QuoteRequest(BaseModel):
    origin_zip: str = Field(..., min_length=3, max_length=10)
    destination_zip: str = Field(..., min_length=3, max_length=10)
    weight_lbs: confloat(gt=0)
    pieces: conint(gt=0)
    dimensions: Dimensions = Field(default_factory=Dimensions)
    special_services: List[str] = Field(default_factory=list)
    pickup_date: str
    commodity: str = ""


class QuoteBreakdown(BaseModel):
    base_rate: float
    fuel_surcharge: float
    liftgate_fee: float
    insurance: float
    climate_control_fee: float
    residential_delivery_fee: float
    special_handling_fee: float
    inside_delivery_fee: float
    white_glove_service_fee: float
    appointment_fee: float
    express_fee: float


class QuoteResponse(BaseModel):
    quote_id: str
    total_cost: float
    breakdown: QuoteBreakdown
    transit_days: int
    equipment_type: str
    valid_until: str
    terms: str


@app.post("/api/v1/quote", response_model=QuoteResponse)
def create_quote(req: QuoteRequest):
    try:
        quote_dict = generate_quote(req.dict())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal pricing error")
    return QuoteResponse(**quote_dict)
