"""
LandFinder — Seed data setup via Supabase Python client.

IMPORTANT: Run setup.sql in the Supabase SQL Editor FIRST to create tables:
  Supabase Dashboard > SQL Editor > New Query > paste setup.sql > Run

This script then seeds the agent config and test parcel.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from functions.db import get_client


def seed_agent_configs():
    supabase = get_client()
    data = {
        "agent_id": "steven_christie",
        "agent_name": "Steven Christie",
        "agent_email": "stevenchristie4@gmail.com",
        "agent_phone": "610-389-2810",
        "brokerage": "Keller Williams Real Estate",
        "target_counties": ["Chester"],
        "min_lot_size_acres": 1.0,
        "max_lot_size_acres": 50.0,
        "min_price": 50000,
        "max_price": 2000000,
        "max_days_on_market": 180,
        "active_channels": ["mail", "email", "sms"],
        "retouch_cadence_days": 28,
        "sample_letters": [],
        "sendgrid_from_email": "stevenchristie4@gmail.com",
    }
    supabase.table("agent_configs").upsert(data).execute()
    print("Agent config seeded for steven_christie")


def seed_parcels():
    supabase = get_client()

    existing = (
        supabase.table("parcels")
        .select("id")
        .eq("mls_id", "MLS123456")
        .execute()
    )
    if existing.data:
        print("Test parcel already exists — skipping insert")
        return

    data = {
        "address": "123 Test Farm Rd",
        "city": "West Chester",
        "state": "PA",
        "zip": "19382",
        "county": "Chester",
        "township": "Birmingham",
        "lot_size_acres": 5.2,
        "list_price": 250000,
        "days_on_market": 45,
        "mls_id": "MLS123456",
        "owner_name": "John Test",
        "owner_mailing_address": "456 Owner St, Philadelphia PA 19103",
        "status": "new",
        "agent_id": "steven_christie",
    }
    supabase.table("parcels").insert(data).execute()
    print("Test parcel seeded (MLS123456)")


if __name__ == "__main__":
    print("=== LandFinder Seed Setup ===\n")
    print("NOTE: Tables must already exist. Run setup.sql in Supabase SQL Editor first.\n")
    seed_agent_configs()
    seed_parcels()
    print("\nSeed complete.")
