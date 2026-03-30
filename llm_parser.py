import os
import json
from datetime import datetime, timedelta

from dotenv import load_dotenv
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted  # NEW

load_dotenv()

GEMINI_MODEL = "gemini-2.5-flash"


class ShipmentParser:
    """Small helper around Gemini to turn an email into structured shipment data."""

    def __init__(self) -> None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set in your environment/.env file")

        genai.configure(api_key=api_key)
        self._model = genai.GenerativeModel(GEMINI_MODEL)
        self.last_error_code = ""
        print(f"[LLM] Using Gemini model: {GEMINI_MODEL}")

    def _build_prompt(self, subject: str, body: str) -> str:
        """Prompt that tells Gemini exactly what JSON we want."""
        return f"""
You are a freight quoting assistant.

Read the email below and return ONLY a JSON object with this exact structure:

{{
  "origin": {{
    "city": "string",
    "state": "string",
    "zip": "string",
    "address": "string"
  }},
  "destination": {{
    "city": "string",
    "state": "string",
    "zip": "string",
    "address": "string"
  }},
  "cargo": {{
    "weight_lbs": number,
    "pieces": number,
    "piece_type": "string",
    "dimensions": {{
      "length": number,
      "width": number,
      "height": number,
      "unit": "inches"
    }},
    "commodity": "string"
  }},
  "special_services": ["string"],
  "pickup_date": "YYYY-MM-DD",
  "additional_notes": "string"
}}

Rules:
- Convert all weights to pounds (lbs).
- Convert all dimensions to inches.
- If the text says things like "tomorrow", "next Tuesday", or "next week",
  convert that to an actual date in YYYY-MM-DD using today as reference.
- If pickup date is missing or says "ASAP" / "earliest available", use tomorrow's date.
- If the commodity or notes mention electronics, pharmaceuticals, medical,
  temperature control, etc., include "climate control" in special_services.
- If liftgate is mentioned, add "liftgate" to special_services.
- If any field is not present, use "" or 0 as a placeholder.

Email subject: {subject}
Email body:
\"\"\"{body}\"\"\"

Return ONLY valid JSON.
Keep the JSON compact.
Do not wrap it in backticks, code blocks, or explanations.
"""

    def _build_retry_prompt(self, subject: str, body: str) -> str:
        return self._build_prompt(subject, body) + """

Important:
- Your previous answer may have been truncated.
- Return the full JSON object on a single line.
- Ensure all braces and brackets are closed.
"""

    def _build_classification_prompt(self, subject: str, body: str) -> str:
        return f"""
You are classifying inbox emails for a freight brokerage assistant.

Decide whether this email is asking for a freight shipping quote or rate.

Return exactly one token:
- QUOTE
- NOT_QUOTE

Treat emails as QUOTE only if the sender is asking for pricing, a freight quote,
or shipment-rate help for moving goods. General customer service, tracking,
delivery updates, invoices, marketing, newsletters, and unrelated business email
should be NOT_QUOTE.

Subject: {subject}
Body:
\"\"\"{body}\"\"\"
"""

    def _call_model(self, prompt: str) -> str:
        """Send the prompt to Gemini and return plain text, or '' on error."""
        try:
            resp = self._model.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.1,
                    "top_p": 0.8,
                    "top_k": 40,
                    "max_output_tokens": 2048,
                },
            )
            text = getattr(resp, "text", None)
            if not text:
                text = str(resp)
            return text.strip()
        except ResourceExhausted as e:
            self.last_error_code = "quota_exhausted"
            print("[LLM] Gemini quota exhausted:", e)
            return ""
        except Exception as e:
            self.last_error_code = "model_error"
            print("[LLM] Gemini error:", e)
            return ""

    def _parse_json_loose(self, raw: str) -> dict | None:
        """Try hard to get a JSON object out of the model text."""
        # 1) Direct parse
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        # 2) If model added markdown ```json blocks, strip them
        if "```" in raw:
            stripped = raw.strip("` \n")
            if stripped.lower().startswith("json"):
                stripped = stripped[4:]
            stripped = stripped.strip()
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                pass

        # 3) Grab first {...} region
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start != -1 and end > start:
            candidate = raw[start:end]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                return None

        return None

    def _normalize_pickup_date(self, pickup_value: str) -> str:
        """Handle 'ASAP', 'tomorrow', etc., into YYYY-MM-DD."""
        if not isinstance(pickup_value, str):
            return datetime.now().strftime("%Y-%m-%d")

        text = pickup_value.lower().strip()
        today = datetime.now()

        if text in ("", "asap", "earliest available"):
            dt = today + timedelta(days=1)
        elif "tomorrow" in text:
            dt = today + timedelta(days=1)
        elif "next week" in text:
            dt = today + timedelta(days=7)
        elif "next tuesday" in text:
            weekday_target = 1  # Tuesday
            days_ahead = (weekday_target - today.weekday() + 7) % 7
            if days_ahead == 0:
                days_ahead = 7
            dt = today + timedelta(days=days_ahead)
        else:
            try:
                dt = datetime.fromisoformat(text)
            except ValueError:
                dt = today

        return dt.strftime("%Y-%m-%d")

    def _postprocess(self, data: dict) -> dict:
        """Ensure all expected keys exist and add inferred services."""
        data.setdefault("origin", {})
        data.setdefault("destination", {})
        data.setdefault("cargo", {})
        data["cargo"].setdefault("dimensions", {})
        data.setdefault("special_services", [])
        data.setdefault("additional_notes", "")

        dims = data["cargo"]["dimensions"]
        dims.setdefault("unit", "inches")
        for key in ("length", "width", "height"):
            try:
                dims[key] = float(dims.get(key, 0) or 0)
            except (TypeError, ValueError):
                dims[key] = 0.0

        for key in ("weight_lbs", "pieces"):
            try:
                data["cargo"][key] = float(data["cargo"].get(key, 0) or 0)
            except (TypeError, ValueError):
                data["cargo"][key] = 0.0

        if data["cargo"]["weight_lbs"] > 0 and data["cargo"]["pieces"] <= 0:
            data["cargo"]["pieces"] = 1

        pickup_raw = data.get("pickup_date", "")
        data["pickup_date"] = self._normalize_pickup_date(pickup_raw)

        raw_services = data.get("special_services", [])
        if isinstance(raw_services, str):
            raw_services = [raw_services]
        elif not isinstance(raw_services, list):
            raw_services = []

        services = {str(service).lower() for service in raw_services if str(service).strip()}
        commodity = str(data["cargo"].get("commodity", "")).lower()
        notes = str(data.get("additional_notes", "")).lower()
        combined = commodity + " " + notes

        if any(k in combined for k in ["electronics", "computer", "pharma", "medical", "temperature"]):
            services.add("climate control")
        if "liftgate" in combined:
            services.add("liftgate")
        if "residential" in combined:
            services.add("residential delivery")

        data["special_services"] = sorted(services)
        return data
    
    def _is_valid_shipment(self, data: dict) -> bool:
        try:
            origin = data["origin"]
            dest = data["destination"]
            cargo = data["cargo"]
        except KeyError:
            print("[LLM] Missing origin/destination/cargo keys")
            return False

        if not origin.get("zip") or not dest.get("zip"):
            print("[LLM] Invalid zips:", origin.get("zip"), dest.get("zip"))
            return False

        if cargo.get("weight_lbs", 0) <= 0:
            print("[LLM] Invalid weight_lbs:", cargo.get("weight_lbs"))
            return False

        if cargo.get("pieces", 0) <= 0:
            print("[LLM] Invalid pieces:", cargo.get("pieces"))
            return False

        return True


    def extract_shipment(self, subject: str, body: str) -> dict | None:
        """Email → structured shipment dict, or None when LLM/unusable."""
        self.last_error_code = ""
        prompt = self._build_prompt(subject, body)
        raw_text = self._call_model(prompt)

        if not raw_text:
            if not self.last_error_code:
                self.last_error_code = "empty_response"
            print("[LLM] No response from model, cannot extract shipment")
            return None

        print("[LLM] Raw model output:", raw_text)
        parsed = self._parse_json_loose(raw_text)
        if not parsed:
            print("[LLM] Could not parse JSON from model output, retrying with compact prompt")
            retry_text = self._call_model(self._build_retry_prompt(subject, body))
            if retry_text:
                print("[LLM] Retry model output:", retry_text)
                parsed = self._parse_json_loose(retry_text)

        if not parsed:
            self.last_error_code = "invalid_json"
            print("[LLM] Could not parse JSON from model output")
            return None

        data = self._postprocess(parsed)

        if not self._is_valid_shipment(data):
            self.last_error_code = "invalid_shipment"
            print("[LLM] Parsed shipment is invalid, not quoting.")
            return None

        return data

    def _heuristic_is_quote_email(self, subject: str, body: str) -> bool | None:
        text = (subject + " " + body).lower()

        negative_keywords = [
            "invoice", "receipt", "payment received", "reminder",
            "newsletter", "unsubscribe", "webinar", "meeting",
            "calendar", "out of office", "automatic reply", "delivered",
            "tracking number", "your order has shipped",
        ]
        if any(keyword in text for keyword in negative_keywords):
            return False

        pricing_signals = ["quote", "rate", "pricing", "price", "estimate"]
        shipment_signals = [
            "freight", "shipment", "ship", "pickup", "delivery",
            "pallet", "skid", "crate", "boxes", "lbs", "kg", "zip",
        ]

        pricing_hits = sum(1 for keyword in pricing_signals if keyword in text)
        shipment_hits = sum(1 for keyword in shipment_signals if keyword in text)

        if pricing_hits >= 1 and shipment_hits >= 1:
            return True
        if shipment_hits >= 3:
            return True
        if pricing_hits == 0 and shipment_hits == 0:
            return False
        return None

    def is_quote_email(self, subject: str, body: str) -> bool:
        """Classify whether this email is a freight quote request."""
        heuristic = self._heuristic_is_quote_email(subject, body)
        if heuristic is not None:
            return heuristic

        raw_text = self._call_model(self._build_classification_prompt(subject, body))
        if not raw_text:
            return False

        decision = raw_text.strip().upper().split()[0]
        return decision == "QUOTE"


if __name__ == "__main__":
    parser = ShipmentParser()
    sample_subject = "Need freight quote from Dallas to Chicago"
    sample_body = """
    Hi team,

    Please quote 2 pallets of electronics from Dallas, TX 75201
    to Chicago, IL 60607. Each pallet is 48x40x60 inches, total
    weight about 1500 lbs. Pickup next Tuesday, residential delivery
    with liftgate required.

    Thanks!
    """
    result = parser.extract_shipment(sample_subject, sample_body)
    print(json.dumps(result, indent=2))
