from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.colors import Color
from datetime import datetime
from typing import Dict, Any
import os


class QuotePDF:
    """Generate a one-page freight quote PDF from shipment + quote data."""

    def __init__(self) -> None:
        self.company_name = "Cargo Quote Assistant"
        self.company_email = "ops@cargo-quote-assistant.com"
        self.company_phone = "+1 (555) 555-1234"
        self.company_website = "www.cargo-quote-assistant.com"

        self.primary_color = Color(0.2, 0.4, 0.6)  # dark blue
        self.accent_color = Color(0.8, 0.2, 0.2)   # red

    def generate(
        self,
        quote: Dict[str, Any],
        shipment: Dict[str, Any],
        output_path: str,
    ) -> str:
        c = canvas.Canvas(output_path, pagesize=letter)
        width, height = letter

        self._header(c, width, height)
        y = height - 120

        self._quote_info(c, quote, y, width)
        y -= 60

        self._shipment_block(c, shipment, y, width)
        y -= 80

        y = self._cost_table(c, quote, y, width)
        y -= 20

        self._total_block(c, quote, y, width)
        y -= 80

        self._terms_footer(c, y, width)

        c.save()
        return output_path

    # ---------- drawing helpers ----------

    def _header(self, c, width, height):
        c.setFillColor(self.primary_color)
        c.setFont("Helvetica-Bold", 20)
        c.drawCentredString(width / 2, height - 40, self.company_name)

        c.setFillColorRGB(0.3, 0.3, 0.3)
        c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(width / 2, height - 65, "FREIGHT QUOTE")

        c.setFont("Helvetica", 7)
        right_x = width - 60
        c.drawRightString(right_x, height - 40, self.company_email)
        c.drawRightString(right_x, height - 52, self.company_phone)
        c.drawRightString(right_x, height - 64, self.company_website)

        c.setStrokeColorRGB(0.7, 0.7, 0.7)
        c.line(72, height - 80, width - 72, height - 80)

    def _quote_info(self, c, quote, y, width):
        c.setFillColorRGB(0, 0, 0)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(72, y, "QUOTE INFORMATION")

        c.setFont("Helvetica", 10)
        quote_id = quote.get("quote_id", "PENDING-ID")
        quote_date = quote.get("quote_date", datetime.now().strftime("%Y-%m-%d"))
        transit_days = quote.get("transit_days", "")
        equipment = quote.get("equipment_type", "")

        c.drawString(72, y - 20, f"Quote ID: {quote_id}")
        c.drawString(72, y - 35, f"Quote Date: {quote_date}")

        right_x = width - 72
        if transit_days:
            c.drawRightString(right_x, y - 20, f"Transit Time: {transit_days} business days")
        if equipment:
            c.drawRightString(right_x, y - 35, f"Equipment: {equipment}")

    def _shipment_block(self, c, shipment, y, width):
        origin = shipment.get("origin", {}) or {}
        destination = shipment.get("destination", {}) or {}
        cargo = shipment.get("cargo", {}) or {}

        c.setFillColorRGB(0, 0, 0)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(72, y, "SHIPMENT DETAILS")

        c.setFont("Helvetica-Bold", 10)
        c.drawString(72, y - 20, "ORIGIN")
        c.drawString(width / 2, y - 20, "DESTINATION")

        c.setFont("Helvetica", 10)
        # Origin
        c.drawString(72, y - 35, f"{origin.get('city', '')}, {origin.get('state', '')} {origin.get('zip', '')}")
        # Destination
        c.drawString(width / 2, y - 35,
                     f"{destination.get('city', '')}, {destination.get('state', '')} {destination.get('zip', '')}")

        # Cargo line
        weight = cargo.get("weight_lbs", 0)
        pieces = cargo.get("pieces", 0)
        commodity = cargo.get("commodity", "")
        c.drawString(72, y - 55, f"Cargo: {pieces} pieces, {weight} lbs, {commodity}")

    def _cost_table(self, c, quote, y, width):
        breakdown = quote.get("breakdown", {}) or {}

        c.setFillColorRGB(0, 0, 0)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(72, y, "COST BREAKDOWN")

        c.setFont("Helvetica-Bold", 10)
        c.drawString(72, y - 25, "DESCRIPTION")
        amount_x = width - 90
        c.drawRightString(amount_x, y - 25, "AMOUNT")

        c.setStrokeColorRGB(0.7, 0.7, 0.7)
        c.line(72, y - 28, width - 72, y - 28)

        items = [
            ("Base Rate", breakdown.get("base_rate", 0.0)),
            ("Fuel Surcharge", breakdown.get("fuel_surcharge", 0.0)),
            ("Climate Control Fee", breakdown.get("climate_control_fee", 0.0)),
            ("Liftgate Fee", breakdown.get("liftgate_fee", 0.0)),
            ("Insurance", breakdown.get("insurance", 0.0)),
            ("Other Accessorials", sum([
                breakdown.get("residential_delivery_fee", 0.0),
                breakdown.get("special_handling_fee", 0.0),
                breakdown.get("inside_delivery_fee", 0.0),
                breakdown.get("white_glove_service_fee", 0.0),
                breakdown.get("appointment_fee", 0.0),
                breakdown.get("express_fee", 0.0),
            ])),
        ]

        c.setFont("Helvetica", 10)
        current_y = y - 45

        for label, amount in items:
            if amount and amount != 0:
                c.drawString(72, current_y, label)
                c.drawRightString(amount_x, current_y, f"${amount:,.2f}")
                current_y -= 18

        return current_y

    def _total_block(self, c, quote, y, width):
        c.setStrokeColorRGB(0, 0, 0)
        c.line(72, y + 25, width - 72, y + 25)

        c.setFillColor(self.accent_color)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(72, y, "TOTAL COST")

        total = quote.get("total_cost", 0.0)
        amount_x = width - 90
        c.drawRightString(amount_x, y, f"${total:,.2f}")

    def _terms_footer(self, c, y, width):
        terms = [
            "Quote is valid for 7 days from date of issue.",
            "Pricing is based on information provided and may change if shipment details differ.",
            "All shipments are subject to carrier availability and standard liability limits.",
            "Additional accessorial charges may apply for services not listed on this quote.",
        ]

        c.setFillColorRGB(0, 0, 0)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(72, y, "TERMS & CONDITIONS")

        c.setFont("Helvetica", 9)
        cur_y = y - 20
        for line in terms:
            if cur_y < 60:
                break
            c.drawString(72, cur_y, f"• {line}")
            cur_y -= 14

        c.setFont("Helvetica", 9)
        c.drawString(
            72,
            40,
            "Thank you for choosing Cargo Quote Assistant for your freight needs.",
        )
        c.drawString(
            72,
            25,
            f"For questions or booking, contact us at {self.company_email}",
        )


if __name__ == "__main__":
    # tiny standalone test
    sample_quote = {
        "quote_id": "QT-20260226-TEST",
        "quote_date": datetime.now().strftime("%Y-%m-%d"),
        "transit_days": 4,
        "equipment_type": "reefer",
        "breakdown": {
            "base_rate": 1112.09,
            "fuel_surcharge": 200.18,
            "climate_control_fee": 175.00,
            "liftgate_fee": 85.00,
            "insurance": 111.21,
        },
        "total_cost": 1683.48,
    }

    sample_shipment = {
        "origin": {"city": "Dallas", "state": "TX", "zip": "75201"},
        "destination": {"city": "Chicago", "state": "IL", "zip": "60607"},
        "cargo": {"weight_lbs": 1500, "pieces": 2, "commodity": "electronics"},
    }

    out = "sample_quote.pdf"
    pdf = QuotePDF()
    pdf.generate(sample_quote, sample_shipment, out)
    print(f"PDF generated: {os.path.abspath(out)}")
