from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict

from pricing_engine import PricingEngine, Location, Cargo

pricer = PricingEngine()


def generate_quote(request_data: Dict[str, Any]) -> Dict[str, Any]:
    origin = Location(
        zip=str(request_data.get("origin_zip", "") or "").strip(),
        city=str(request_data.get("origin_city", "") or "").strip(),
        state=str(request_data.get("origin_state", "") or "").strip(),
    )
    destination = Location(
        zip=str(request_data.get("destination_zip", "") or "").strip(),
        city=str(request_data.get("destination_city", "") or "").strip(),
        state=str(request_data.get("destination_state", "") or "").strip(),
    )

    cargo = Cargo(
        weight_lbs=float(request_data.get("weight_lbs", 0) or 0),
        pieces=int(float(request_data.get("pieces", 0) or 0)),
        commodity=str(request_data.get("commodity", "") or ""),
        special_services=list(request_data.get("special_services", []) or []),
        additional_notes=str(request_data.get("additional_notes", "") or ""),
    )

    quote_dict = pricer.price(
        origin=origin,
        destination=destination,
        cargo=cargo,
        pickup_date=str(request_data.get("pickup_date", "") or ""),
    )

    breakdown = quote_dict.get("breakdown", {})
    valid_until = quote_dict.get("valid_until")
    if not valid_until:
        valid_until = (datetime.utcnow() + timedelta(days=7)).isoformat() + "Z"

    return {
        "quote_id": f"QT-{datetime.utcnow().strftime('%Y%m%d-%H%M%S-%f')}",
        "total_cost": float(quote_dict.get("total_cost", 0.0)),
        "breakdown": {
            "base_rate": float(breakdown.get("base_rate", 0.0)),
            "fuel_surcharge": float(breakdown.get("fuel_surcharge", 0.0)),
            "liftgate_fee": float(breakdown.get("liftgate_fee", 0.0)),
            "insurance": float(breakdown.get("insurance", 0.0)),
            "climate_control_fee": float(breakdown.get("climate_control_fee", 0.0)),
            "residential_delivery_fee": float(breakdown.get("residential_delivery_fee", 0.0)),
            "special_handling_fee": float(breakdown.get("special_handling_fee", 0.0)),
            "inside_delivery_fee": float(breakdown.get("inside_delivery_fee", 0.0)),
            "white_glove_service_fee": float(breakdown.get("white_glove_service_fee", 0.0)),
            "appointment_fee": float(breakdown.get("appointment_fee", 0.0)),
            "express_fee": float(breakdown.get("express_fee", 0.0)),
        },
        "transit_days": int(quote_dict.get("transit_days", 0)),
        "equipment_type": quote_dict.get("equipment_type", "dry_van"),
        "valid_until": valid_until,
        "terms": quote_dict.get("terms", "Payment due upon delivery."),
    }
