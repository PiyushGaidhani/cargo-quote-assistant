#!/usr/bin/env python3
"""
Database query tool for viewing freight quotes and statistics.
Uses QuoteDatabase from quote_database.py.
"""

import sys
from quote_database import QuoteDatabase


def print_quote_details(quote: dict) -> None:
    """Pretty-print a single quote row with key details."""
    print()
    print(f"📦 Quote ID: {quote.get('quote_id')}")
    print(f"👤 Customer: {quote.get('customer_name') or 'N/A'} ({quote.get('customer_email')})")
    print(f"📧 Subject: {quote.get('subject')}")
    print(
        "📍 Route: "
        f"{quote.get('origin_city')}, {quote.get('origin_state')} "
        f"→ {quote.get('destination_city')}, {quote.get('destination_state')}"
    )
    print(f"⚖️  Shipment: {quote.get('weight_lbs')} lbs, {quote.get('pieces')} pieces")
    print(f"🧱 Commodity: {quote.get('commodity')}")
    print(f"💰 Total Cost: ${quote.get('total_cost', 0):.2f}")
    print(f"🚚 Transit: {quote.get('transit_days')} days")
    print(f"📄 PDF: {quote.get('pdf_path')}")
    print(f"⏰ Created: {quote.get('created_at')}")
    print(f"📊 Status: {quote.get('status')}")
    print()


def cmd_recent(db: QuoteDatabase, limit: int = 10) -> None:
    quotes = db.get_recent_quotes(limit)
    print(f"\n📋 Last {len(quotes)} quotes:")
    print("-" * 100)
    print(f"{'QUOTE ID':18} | {'CUSTOMER':22} | {'TOTAL':>10} | {'CREATED AT':19} | STATUS")
    print("-" * 100)
    for row in quotes:
        quote_id, customer_email, customer_name, subject, total_cost, created_at, status = row
        name_display = customer_name or customer_email or "N/A"
        print(
            f"{quote_id:18} | {name_display[:22]:22} | "
            f"${total_cost:>9.2f} | {created_at:19} | {status}"
        )


def cmd_customer(db: QuoteDatabase, email: str) -> None:
    quotes = db.get_quotes_by_email(email)
    print(f"\n📧 Quotes for {email}:")
    if not quotes:
        print("  (none)")
        return
    for row in quotes:
        quote_id, customer_name, subject, total_cost, created_at, status = row
        print(
            f"  {quote_id} | {subject[:30]:30} | "
            f"${total_cost:8.2f} | {created_at} | {status}"
        )


def cmd_quote(db: QuoteDatabase, quote_id: str) -> None:
    quote = db.get_quote(quote_id)
    if quote:
        print_quote_details(quote)
    else:
        print(f"Quote {quote_id} not found")


def cmd_stats(db: QuoteDatabase) -> None:
    stats = db.get_statistics()
    print("\n📊 Database Statistics")
    print("-" * 40)
    print(f"Total Quotes: {stats.get('total_quotes', 0)}")

    print("\nBy Status:")
    for status, count in stats.get("quotes_by_status", {}).items():
        print(f"  {status}: {count}")

    print("\nRecent Activity (last 7 days):")
    for date, count in stats.get("recent_activity", {}).items():
        print(f"  {date}: {count} quotes")

    print("\n🏆 Top Customers:")
    for email, count in stats.get("top_customers", []):
        print(f"  {email}: {count} quotes")


def print_help() -> None:
    print(
        """
Database Query Tool

Usage:
  python query_database.py recent [limit]    - Show recent quotes (default: 10)
  python query_database.py customer <email>  - Show quotes for a customer email
  python query_database.py quote <quote_id>  - Show full details for one quote
  python query_database.py stats             - Show database statistics

Examples:
  python query_database.py recent 5
  python query_database.py customer john@example.com
  python query_database.py quote QT-20260226-ABC123
  python query_database.py stats
"""
    )


def main() -> None:
    db = QuoteDatabase()

    if len(sys.argv) < 2:
        print_help()
        return

    command = sys.argv[1].lower()

    if command == "recent":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        cmd_recent(db, limit)
    elif command == "customer":
        if len(sys.argv) < 3:
            print("Please provide customer email")
            return
        cmd_customer(db, sys.argv[2])
    elif command == "quote":
        if len(sys.argv) < 3:
            print("Please provide quote ID")
            return
        cmd_quote(db, sys.argv[2])
    elif command == "stats":
        cmd_stats(db)
    else:
        print_help()


if __name__ == "__main__":
    main()
