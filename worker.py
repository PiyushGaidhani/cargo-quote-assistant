import os
import json
import logging

from email_client import (
    extract_email_address,
    fetch_recent_unread,
    send_reply_with_attachment,
    mark_message_read,
)
from llm_parser import ShipmentParser
from pricing_engine import Location, Cargo
from pdf_generator import QuotePDF
from quote_database import QuoteDatabase
from last_run_tracker import LastRunTracker
from logging_setup import setup_logging
from quote_service import generate_quote

logger = logging.getLogger(__name__)


def _mark_email_completed(tracker: LastRunTracker, email_id: str) -> None:
    tracker.mark_email_processed(email_id)
    try:
        mark_message_read(email_id)
    except Exception as ex:
        logger.warning("Failed to mark email %s as read: %s", email_id, ex)


def process_emails():
    parser = ShipmentParser()
    pdf_maker = QuotePDF()
    db = QuoteDatabase()
    tracker = LastRunTracker(log_file="last_run.json")

    os.makedirs("quotes", exist_ok=True)

    already_processed = tracker.get_processed_emails()
    emails = fetch_recent_unread(limit=25)

    for email in emails:
        email_id = email.get("id", "")

        # 0) skip if this email id was already handled in a previous run
        if email_id in already_processed:
            try:
                mark_message_read(email_id)
            except Exception as ex:
                logger.warning("Failed to mark already-processed email %s as read: %s", email_id, ex)
            continue

        subject = email.get("subject", "")
        body = email.get("body", "")

        # 1) classify as freight quote
        if not parser.is_quote_email(subject, body):
            _mark_email_completed(tracker, email_id)
            continue

        print("-----")
        print("From:", email.get("from"))
        print("Subject:", subject)

        # 2) extract shipment
        shipment = parser.extract_shipment(subject, body)
        print("Shipment data:", json.dumps(shipment, indent=2) if shipment else shipment)

        if shipment is None:
            if parser.last_error_code in {"quota_exhausted", "model_error", "empty_response"}:
                logger.warning(
                    "Skipping email %s without marking processed because extraction failed transiently (%s)",
                    email_id,
                    parser.last_error_code,
                )
                continue

            # Do not price. Send a clarification email only for parseable-but-incomplete requests.
            to_address = email.get("from_email") or extract_email_address(email.get("from", ""))
            thread_id = email.get("threadId", email.get("id", ""))

            # Best-effort summary of what we understood so far.
            origin = (shipment or {}).get("origin", {}) if shipment else {}
            destination = (shipment or {}).get("destination", {}) if shipment else {}
            cargo = (shipment or {}).get("cargo", {}) if shipment else {}

            origin_str = ", ".join(
                part for part in [
                    origin.get("city", ""),
                    origin.get("state", ""),
                    origin.get("zip", ""),
                ] if part
            )
            dest_str = ", ".join(
                part for part in [
                    destination.get("city", ""),
                    destination.get("state", ""),
                    destination.get("zip", ""),
                ] if part
            )

            pieces = cargo.get("pieces", None)
            weight_lbs = cargo.get("weight_lbs", None)

            parsed_bits = []
            if origin_str:
                parsed_bits.append(f"- Origin (so far): {origin_str}")
            if dest_str:
                parsed_bits.append(f"- Destination (so far): {dest_str}")
            if pieces:
                parsed_bits.append(f"- Pieces: {pieces}")
            if weight_lbs:
                parsed_bits.append(f"- Weight: {weight_lbs} lbs")

            parsed_section = ""
            if parsed_bits:
                parsed_section = (
                    "Here’s what I was able to understand from your email:\n"
                    + "\n".join(parsed_bits)
                    + "\n\n"
                )

            reply_body = (
                "Hi,\n\n"
                "Thanks for reaching out for a freight quote.\n\n"
                "I was not able to reliably extract all the details needed "
                "to generate a quote from your email.\n\n"
                f"{parsed_section}"
                "Could you please confirm the following information?\n"
                "- Origin city, state, and zip\n"
                "- Destination city, state, and zip\n"
                "- Total weight (in lbs)\n"
                "- Number of pallets/skids and basic dimensions\n"
                "- Desired pickup date\n\n"
                "Reply to this email with these details and I’ll send an updated quote.\n\n"
                "Best regards,\n"
                "Cargo Quote Assistant"
            )


            try:
                send_reply_with_attachment(
                    thread_id=thread_id,
                    to_address=to_address,
                    original_subject=subject,
                    body_text=reply_body,
                    pdf_path=None,  # no attachment on error
                    in_reply_to=email.get("message_id"),
                )
                print("Missing-info reply sent (no quote).")
            except Exception as ex:
                print("Failed to send missing-info reply:", ex)
                logger.warning("Leaving email %s unprocessed so clarification can be retried", email_id)
                continue

            _mark_email_completed(tracker, email_id)
            continue

        # 3) build pricing inputs (for logging/convenience)
        origin = Location(
            zip=shipment.get("origin", {}).get("zip", ""),
            city=shipment.get("origin", {}).get("city", ""),
            state=shipment.get("origin", {}).get("state", ""),
        )
        dest = Location(
            zip=shipment.get("destination", {}).get("zip", ""),
            city=shipment.get("destination", {}).get("city", ""),
            state=shipment.get("destination", {}).get("state", ""),
        )
        cargo = Cargo(
            weight_lbs=shipment.get("cargo", {}).get("weight_lbs", 0),
            pieces=shipment.get("cargo", {}).get("pieces", 0),
            commodity=shipment.get("cargo", {}).get("commodity", ""),
            special_services=shipment.get("special_services", []),
            additional_notes=shipment.get("additional_notes", ""),
        )

        # 4) build quote locally through shared quote logic
        dims = shipment.get("cargo", {}).get("dimensions", {})
        payload = {
            "origin_zip": origin.zip,
            "origin_city": origin.city,
            "origin_state": origin.state,
            "destination_zip": dest.zip,
            "destination_city": dest.city,
            "destination_state": dest.state,
            "weight_lbs": cargo.weight_lbs,
            "pieces": cargo.pieces,
            "dimensions": {
                "length": max(float(dims.get("length", 0) or 0), 0),
                "width": max(float(dims.get("width", 0) or 0), 0),
                "height": max(float(dims.get("height", 0) or 0), 0),
            },
            "special_services": cargo.special_services or [],
            "pickup_date": shipment.get("pickup_date", ""),
            "commodity": cargo.commodity,
            "additional_notes": cargo.additional_notes,
        }

        try:
            quote = generate_quote(payload)
        except Exception as ex:
            print("Quote generation failed:", ex)
            logger.warning("Quote generation failed for email %s; leaving it unprocessed for retry", email_id)
            continue
        print("Quote:", json.dumps(quote, indent=2))

        # 5) PDF
        quote_id = quote.get("quote_id", "quote")
        pdf_filename = f"{quote_id}.pdf"
        pdf_path = os.path.join("quotes", pdf_filename)
        pdf_maker.generate(quote, shipment, pdf_path)
        print("PDF saved to:", pdf_path)

        # 6) DB
        saved = db.save_quote(
            quote_data=quote,
            shipment_data=shipment,
            email_data=email,
            pdf_path=pdf_path,
        )
        print("Saved to DB:", saved)

        # 7) reply with PDF quote and a short lane summary
        origin_city = shipment.get("origin", {}).get("city", "")
        origin_state = shipment.get("origin", {}).get("state", "")
        origin_zip = shipment.get("origin", {}).get("zip", "")

        dest_city = shipment.get("destination", {}).get("city", "")
        dest_state = shipment.get("destination", {}).get("state", "")
        dest_zip = shipment.get("destination", {}).get("zip", "")

        pieces = shipment.get("cargo", {}).get("pieces", 0)
        weight_lbs = shipment.get("cargo", {}).get("weight_lbs", 0)

        lane_summary = (
            f"Lane: {origin_city}, {origin_state} {origin_zip} → "
            f"{dest_city}, {dest_state} {dest_zip}, "
            f"{pieces} pieces, {weight_lbs} lbs."
        )

        reply_body = (
            "Hi,\n\n"
            "Please find attached your freight quote generated by Cargo Quote Assistant.\n\n"
            f"{lane_summary}\n"
            f"Total cost: ${quote.get('total_cost', 0):.2f}\n"
            f"Transit time: {quote.get('transit_days', '')} business days\n\n"
            "Reply to this email if you have any questions or need to book this shipment.\n\n"
            "Best regards,\n"
            "Cargo Quote Assistant"
        )


        to_address = email.get("from_email") or extract_email_address(email.get("from", ""))
        thread_id = email.get("threadId", email.get("id", ""))

        try:
            send_reply_with_attachment(
                thread_id=thread_id,
                to_address=to_address,
                original_subject=subject,
                body_text=reply_body,
                pdf_path=pdf_path,
                in_reply_to=email.get("message_id"),
            )
            print("Reply sent with PDF attached.")
        except Exception as ex:
            print("Failed to send reply:", ex)
            logger.warning("Reply send failed for email %s; leaving it unprocessed for retry", email_id)
            continue

        # 8) mark email as processed
        _mark_email_completed(tracker, email_id)

    # update last run time
    tracker.update_last_run_time()


if __name__ == "__main__":
    setup_logging()
    process_emails()
