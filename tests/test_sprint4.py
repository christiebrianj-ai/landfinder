"""
LandFinder — Sprint 4 test suite.

Tests outreach generation (mail, email, SMS), A/B versioning,
LLC salutation formatting, response recording, and A/B tracker.
"""

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s — %(message)s")

from functions.db import get_client
from functions.outreach_generator import generate_outreach
from functions.ab_tracker import record_response, get_ab_performance


DIVIDER = "─" * 70


def print_section(title):
    print(f"\n{'═' * 70}")
    print(f"  {title}")
    print(f"{'═' * 70}\n")


def run_tests():
    print_section("LandFinder Sprint 4 Tests")

    supabase = get_client()

    # ── Setup: get seed parcel ───────────────────────────────────────────────
    result = supabase.table("parcels").select("*").eq("mls_id", "MLS123456").execute()
    assert result.data, "Seed parcel MLS123456 not found"
    parcel_id = result.data[0]["id"]
    print(f"Seed parcel ID: {parcel_id}")

    # Update with realistic test data
    supabase.table("parcels").update({
        "owner_name": "George & Martha Williams",
        "owner_mailing_address": "456 Owner Lane, Philadelphia PA 19103",
        "township": "Birmingham",
        "lot_size_acres": 5.2,
        "opportunity_score": 75,
        "score_reasoning": "Out of state owner, long days on market, sweet spot acreage",
    }).eq("id", parcel_id).execute()
    print("Seed parcel updated with test data\n")

    # ── TEST 1: Mail letter, Version A ───────────────────────────────────────
    print_section("TEST 1 — Mail letter, Version A (buyer angle)")

    result = generate_outreach(parcel_id, "steven_christie", "mail", touch_number=1, version="A")
    assert result, "generate_outreach returned None"

    print(f"VERSION:   {result['version']}")
    print(f"HOOK TYPE: {result['hook_type']}")
    print(f"\n{DIVIDER}\n")
    print(result["body"])
    print(f"\n{DIVIDER}")

    body = result["body"]
    assert "George" in body,        "Missing owner first name"
    assert "5.2" in body,           "Missing acreage"
    assert "Birmingham" in body,    "Missing township"
    assert "P.S." in body,          "Missing P.S. line"
    assert "610-389-2810" in body,  "Missing Steven's phone number"
    print("\nAll content assertions passed ✓\n")

    # ── TEST 2: Email, Version A ─────────────────────────────────────────────
    print_section("TEST 2 — Email, Version A (buyer angle)")

    result = generate_outreach(parcel_id, "steven_christie", "email", touch_number=1, version="A")
    assert result, "generate_outreach returned None"

    print(f"VERSION:   {result['version']}")
    print(f"HOOK TYPE: {result['hook_type']}")
    print(f"SUBJECT:   {result['subject']}\n")
    print(f"{DIVIDER}\n")
    print(result["body"])
    print(f"\n{DIVIDER}")
    print("\nEmail generated ✓\n")

    # ── TEST 3: SMS, Version A ───────────────────────────────────────────────
    print_section("TEST 3 — SMS, Version A (buyer angle)")

    result = generate_outreach(parcel_id, "steven_christie", "sms", touch_number=1, version="A")
    assert result, "generate_outreach returned None"

    print(f"VERSION:   {result['version']}")
    print(f"HOOK TYPE: {result['hook_type']}")
    print(f"\nSMS TEXT:\n{result['body']}\n")
    char_count = len(result["body"])
    print(f"Character count: {char_count}/160")
    assert char_count <= 160, f"SMS exceeds 160 characters: {char_count}"
    print("Character count ≤ 160 ✓\n")

    # ── TEST 4: Mail letter, Version B (forced) ──────────────────────────────
    print_section("TEST 4 — Mail letter, Version B (market activity angle)")

    result_b = generate_outreach(parcel_id, "steven_christie", "mail", touch_number=1, version="B")
    assert result_b, "generate_outreach returned None"

    print(f"VERSION:   {result_b['version']}")
    print(f"HOOK TYPE: {result_b['hook_type']}")
    print(f"\n{DIVIDER}\n")
    print(result_b["body"])
    print(f"\n{DIVIDER}")

    assert result_b["hook_type"] == "market_activity_angle", (
        f"Expected market_activity_angle, got {result_b['hook_type']}"
    )
    print("\nVersion B uses market_activity_angle hook ✓\n")

    # ── TEST 5: LLC owner salutation ─────────────────────────────────────────
    print_section("TEST 5 — LLC owner salutation formatting")

    supabase.table("parcels").update(
        {"owner_name": "Wylie Road Holdings LLC"}
    ).eq("id", parcel_id).execute()

    result = generate_outreach(parcel_id, "steven_christie", "mail", touch_number=1, version="A")
    assert result, "generate_outreach returned None"

    print(f"\n{DIVIDER}\n")
    print(result["body"])
    print(f"\n{DIVIDER}\n")

    assert "To the attention of" in result["body"], (
        "LLC salutation 'To the attention of' not found in letter"
    )
    assert "Dear" not in result["body"].split("\n\n")[2] if "\n\n" in result["body"] else True, \
        "Should not use 'Dear' for LLC"
    print("LLC salutation 'To the attention of' confirmed ✓")

    # Reset owner name
    supabase.table("parcels").update(
        {"owner_name": "George & Martha Williams"}
    ).eq("id", parcel_id).execute()
    print("Owner name reset to George & Martha Williams\n")

    # ── TEST 6: Record response, check A/B tracker ───────────────────────────
    print_section("TEST 6 — Record response and check parcel escalation")

    # Insert a touchpoint to respond to
    supabase.table("touchpoints").insert({
        "parcel_id": parcel_id,
        "channel": "mail",
        "content": "Sprint 4 test letter",
        "touch_number": 1,
        "version": "A",
        "response_received": False,
        "responded": False,
    }).execute()

    tp_row = record_response(parcel_id, "mail", "Owner called back, interested in offer")
    assert tp_row, "record_response returned None"

    print("Returned touchpoint row:")
    for k, v in tp_row.items():
        print(f"  {k}: {v}")

    # Confirm parcel escalated
    parcel_check = (
        supabase.table("parcels").select("status").eq("id", parcel_id).execute().data[0]
    )
    assert parcel_check["status"] == "escalated", (
        f"Expected 'escalated', got '{parcel_check['status']}'"
    )
    print(f"\nParcel status: {parcel_check['status']} ✓\n")

    # ── TEST 7: A/B performance — not enough data ────────────────────────────
    print_section("TEST 7 — A/B performance (insufficient data)")

    perf = get_ab_performance("steven_christie")
    print(f"get_ab_performance returned:\n{perf}\n")
    assert "insight" in perf, "Missing 'insight' key in response"
    assert "20 sends" in perf["insight"] or "Not enough" in perf["insight"], (
        "Expected not-enough-data message"
    )
    print("Not-enough-data guard working correctly ✓\n")

    # ── Letters table summary ────────────────────────────────────────────────
    print_section("Letters table — draft count and version breakdown")

    all_letters = (
        supabase.table("letters")
        .select("version, hook_type, status")
        .eq("parcel_id", parcel_id)
        .execute()
    )
    letters = all_letters.data or []
    drafts = [l for l in letters if l.get("status") == "draft"]
    version_counts = {}
    for l in drafts:
        v = l.get("version", "A")
        version_counts[v] = version_counts.get(v, 0) + 1

    print(f"Total draft letters for seed parcel: {len(drafts)}")
    for v, count in sorted(version_counts.items()):
        print(f"  Version {v}: {count} letter(s)")
    print()

    print("Sprint 4 test complete")


if __name__ == "__main__":
    run_tests()
