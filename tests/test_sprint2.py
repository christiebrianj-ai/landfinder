"""
LandFinder — Sprint 2 test suite.

Verifies:
  - get_satellite_image() builds and saves a valid Google Maps URL
  - The URL returns a 200 HTTP response (confirms API key is working)
  - enrich_owner() returns existing values without calling an external API
    when owner_email and owner_phone are already populated
"""

import logging
import os
import sys

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s — %(message)s")

from functions.db import get_client
from functions.satellite import get_satellite_image
from functions.owner_research import enrich_owner


def run_tests():
    print("=== LandFinder Sprint 2 Tests ===\n")

    supabase = get_client()

    # ── Get seed parcel ──────────────────────────────────────────────────────
    result = supabase.table("parcels").select("*").eq("mls_id", "MLS123456").execute()
    assert result.data, "Seed parcel MLS123456 not found — run setup.sql first"
    parcel = result.data[0]
    parcel_id = parcel["id"]
    print(f"Seed parcel ID: {parcel_id}\n")

    # ── Satellite image ──────────────────────────────────────────────────────
    print("--- Satellite Image ---")
    url = get_satellite_image(parcel_id)
    print(f"URL: {url}\n")

    assert url, "get_satellite_image() returned None"

    response = requests.get(url)
    print(f"HTTP response: {response.status_code}")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    print("Google Maps API: OK\n")

    # ── Owner research ───────────────────────────────────────────────────────
    print("--- Owner Research ---")
    supabase.table("parcels").update({
        "owner_email": "test@test.com",
        "owner_phone": "+15005550006",
    }).eq("id", parcel_id).execute()
    print("Set fake owner_email and owner_phone on seed parcel")

    contact = enrich_owner(parcel_id)
    print(f"enrich_owner returned: {contact}")
    assert contact is not None, "Expected existing contact dict, got None"
    assert contact["owner_email"] == "test@test.com"
    assert contact["owner_phone"] == "+15005550006"
    print("enrich_owner correctly returned existing values — no external API called\n")

    # ── Full parcel row ──────────────────────────────────────────────────────
    print("--- Full Parcel Row ---")
    result = supabase.table("parcels").select("*").eq("id", parcel_id).execute()
    parcel = result.data[0]
    for key, value in parcel.items():
        print(f"  {key}: {value}")

    assert parcel.get("satellite_image_url"), "satellite_image_url not set"
    assert parcel.get("owner_email") == "test@test.com", "owner_email not set"
    assert parcel.get("owner_phone") == "+15005550006", "owner_phone not set"

    print("\nSprint 2 test complete")


if __name__ == "__main__":
    run_tests()
