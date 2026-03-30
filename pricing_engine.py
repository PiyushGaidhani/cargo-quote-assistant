from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Dict, Any


@dataclass
class Location:
    zip: str
    city: str = ""
    state: str = ""


@dataclass
class Cargo:
    weight_lbs: float
    pieces: int
    commodity: str = ""
    special_services: List[str] | None = None
    additional_notes: str = ""


@dataclass
class QuoteBreakdown:
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

    @property
    def total(self) -> float:
        return round(
            self.base_rate
            + self.fuel_surcharge
            + self.liftgate_fee
            + self.insurance
            + self.climate_control_fee
            + self.residential_delivery_fee
            + self.special_handling_fee
            + self.inside_delivery_fee
            + self.white_glove_service_fee
            + self.appointment_fee
            + self.express_fee,
            2,
        )


class PricingEngine:
    """Price a shipment using simple distance + accessorial rules, inspired by LTL pricing."""

    # Small zip → (lat, lng) catalog (in miles, similar idea to your reference)
    ZIP_COORDS: Dict[str, tuple[float, float]] = {
        "90021": (34.017, -118.243),  # LA
        "60601": (41.885, -87.622),   # Chicago
        "10001": (40.750, -73.997),   # NYC
        "75201": (32.776, -96.796),   # Dallas
        "19102": (39.950, -75.166),   # Philadelphia
        "55401": (44.977, -93.265),   # Minneapolis
        "73301": (30.267, -97.743),   # Austin
        "77001": (29.750, -95.362),   # Houston
        "85001": (33.450, -112.067),  # Phoenix
        "33101": (25.761, -80.191),   # Miami
    }
    REGION_COORDS: Dict[str, tuple[float, float]] = {
        "0": (42.36, -71.06),    # Northeast
        "1": (39.95, -75.16),
        "2": (38.90, -77.03),
        "3": (33.75, -84.39),    # Southeast
        "4": (39.10, -84.51),
        "5": (44.98, -93.27),    # Upper Midwest
        "6": (41.88, -87.63),
        "7": (32.78, -96.80),    # South / TX
        "8": (39.74, -104.99),   # Mountain
        "9": (34.05, -118.24),   # West Coast
    }
    STATE_COORDS: Dict[str, tuple[float, float]] = {
        "AL": (32.37, -86.30),
        "AK": (58.30, -134.42),
        "AZ": (33.45, -112.07),
        "AR": (34.75, -92.29),
        "CA": (38.58, -121.49),
        "CO": (39.74, -104.99),
        "CT": (41.76, -72.67),
        "DE": (39.16, -75.52),
        "FL": (30.44, -84.28),
        "GA": (33.75, -84.39),
        "HI": (21.31, -157.86),
        "ID": (43.62, -116.20),
        "IL": (39.80, -89.65),
        "IN": (39.77, -86.16),
        "IA": (41.59, -93.62),
        "KS": (39.05, -95.67),
        "KY": (38.20, -84.87),
        "LA": (30.45, -91.14),
        "ME": (44.31, -69.78),
        "MD": (38.98, -76.49),
        "MA": (42.36, -71.06),
        "MI": (42.73, -84.55),
        "MN": (44.95, -93.09),
        "MS": (32.30, -90.18),
        "MO": (38.58, -92.17),
        "MT": (46.59, -112.04),
        "NE": (40.81, -96.68),
        "NV": (39.16, -119.77),
        "NH": (43.21, -71.54),
        "NJ": (40.22, -74.76),
        "NM": (35.68, -105.94),
        "NY": (42.65, -73.75),
        "NC": (35.78, -78.64),
        "ND": (46.81, -100.78),
        "OH": (39.96, -83.00),
        "OK": (35.47, -97.52),
        "OR": (44.94, -123.03),
        "PA": (40.27, -76.88),
        "RI": (41.82, -71.41),
        "SC": (34.00, -81.03),
        "SD": (44.37, -100.35),
        "TN": (36.16, -86.78),
        "TX": (30.27, -97.74),
        "UT": (40.76, -111.89),
        "VT": (44.26, -72.58),
        "VA": (37.54, -77.43),
        "WA": (47.04, -122.89),
        "WV": (38.35, -81.63),
        "WI": (43.07, -89.40),
        "WY": (41.14, -104.82),
        "DC": (38.90, -77.04),
    }

    def _coords_for_zip(self, zip_code: str) -> tuple[float, float] | None:
        zip_code = (zip_code or "").strip()
        if zip_code in self.ZIP_COORDS:
            return self.ZIP_COORDS[zip_code]
        if len(zip_code) >= 1 and zip_code[0].isdigit():
            return self.REGION_COORDS.get(zip_code[0])
        return None

    def _coords_for_location(self, location: Location) -> tuple[float, float] | None:
        zip_coords = self._coords_for_zip(location.zip)
        if location.zip in self.ZIP_COORDS:
            return zip_coords

        state = (location.state or "").strip().upper()
        if state in self.STATE_COORDS:
            return self.STATE_COORDS[state]

        return zip_coords

    def _haversine_miles(self, a: Location, b: Location) -> float:
        """Approximate distance between two zips in miles."""
        import math as _m

        coords_a = self._coords_for_location(a)
        coords_b = self._coords_for_location(b)
        if not coords_a or not coords_b:
            return 500.0

        lat1, lon1 = coords_a
        lat2, lon2 = coords_b

        lat1, lon1 = _m.radians(lat1), _m.radians(lon1)
        lat2, lon2 = _m.radians(lat2), _m.radians(lon2)

        dlat = lat2 - lat1
        dlon = lon2 - lon1

        h = _m.sin(dlat / 2) ** 2 + _m.cos(lat1) * _m.cos(lat2) * _m.sin(dlon / 2) ** 2
        c = 2 * _m.asin(_m.sqrt(h))
        radius = 3958.8  # miles

        return radius * c

    def _base_rate(self, distance_miles: float, weight_lbs: float) -> float:
        # Slightly opinionated but simple rule:
        # min $200, 0.65 per mile + 0.08 per lb
        return max(200.0, distance_miles * 0.65 + weight_lbs * 0.08)

    def _insurance_factor(self, commodity: str) -> float:
        commodity = commodity.lower()
        high_value = [
            "electronics",
            "pharmaceutical",
            "medical",
            "art",
            "high value",
            "enterprise it",
        ]
        return 0.10 if any(k in commodity for k in high_value) else 0.04

    def _accessorials(
        self, services: List[str], commodity: str, notes: str
    ) -> QuoteBreakdown:
        s = [x.lower() for x in services]
        notes = notes.lower()

        liftgate_fee = 85.0 if "liftgate" in s else 0.0
        climate_fee = 175.0 if "climate control" in s else 0.0
        residential_fee = 65.0 if any(x in s for x in ["residential", "residential delivery"]) else 0.0
        handling_fee = 95.0 if "special handling" in s else 0.0
        inside_fee = 45.0 if "inside delivery" in s else 0.0
        white_glove_fee = 120.0 if any(x in s for x in ["white glove", "white glove service"]) else 0.0
        appointment_fee = 35.0 if "appointment" in s else 0.0

        express_keywords = ["urgent", "express", "expedited", "priority"]
        express_fee = 200.0 if any(k in notes for k in express_keywords) else 0.0

        # Placeholders for pieces that depend on base_rate; set to 0 here,
        # will be filled after base_rate is known.
        return QuoteBreakdown(
            base_rate=0.0,
            fuel_surcharge=0.0,
            liftgate_fee=liftgate_fee,
            insurance=0.0,
            climate_control_fee=climate_fee,
            residential_delivery_fee=residential_fee,
            special_handling_fee=handling_fee,
            inside_delivery_fee=inside_fee,
            white_glove_service_fee=white_glove_fee,
            appointment_fee=appointment_fee,
            express_fee=express_fee,
        )

    def price(
        self,
        origin: Location,
        destination: Location,
        cargo: Cargo,
        pickup_date: str,
    ) -> Dict[str, Any]:
        """Main entry: compute quote and return plain dict."""
        distance = self._haversine_miles(origin, destination)

        base = self._base_rate(distance, cargo.weight_lbs)
        access = self._accessorials(
            cargo.special_services or [], cargo.commodity, cargo.additional_notes
        )

        fuel = base * 0.18
        insurance = base * self._insurance_factor(cargo.commodity)

        access.base_rate = round(base, 2)
        access.fuel_surcharge = round(fuel, 2)
        access.insurance = round(insurance, 2)

        total = access.total

        # Simple equipment selection
        normalized_services = {service.lower() for service in (cargo.special_services or [])}
        if "climate control" in normalized_services:
            equipment = "reefer"
        elif cargo.weight_lbs > 10000:
            equipment = "flatbed"
        else:
            equipment = "dry_van"

        # Transit days ~ 450 miles/day, clamped
        transit_days = max(2, min(14, int(distance / 450) + 1))
        if access.express_fee > 0:
            transit_days = max(1, transit_days - 2)

        valid_until = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S")

        return {
            "pricing_distance_miles": round(distance, 1),
            "equipment_type": equipment,
            "transit_days": transit_days,
            "pickup_date": pickup_date,
            "breakdown": {
                "base_rate": access.base_rate,
                "fuel_surcharge": access.fuel_surcharge,
                "liftgate_fee": access.liftgate_fee,
                "insurance": access.insurance,
                "climate_control_fee": access.climate_control_fee,
                "residential_delivery_fee": access.residential_delivery_fee,
                "special_handling_fee": access.special_handling_fee,
                "inside_delivery_fee": access.inside_delivery_fee,
                "white_glove_service_fee": access.white_glove_service_fee,
                "appointment_fee": access.appointment_fee,
                "express_fee": access.express_fee,
            },
            "total_cost": total,
            "currency": "USD",
            "valid_until": valid_until,
            "terms": "Payment due upon delivery. Quote valid for 7 days. Subject to carrier availability.",
        }
