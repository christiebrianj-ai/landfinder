"""
LandFinder — Sprint 3 test suite.

Tests three agent_decide() scenarios against the seed parcel:
  A. No touchpoints        → send_initial_outreach
  B. 2 touches, 5 days ago → wait            (within retouch cadence)
  C. 2 touches, 35 days ago → send_monthly_retouch (past retouch cadence)
"""

import logging
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s — %(message)s")

from functions.db import get_client
from functions.agent_brain import agent_decide


def get_latest_reasoning(supabase, parcel_id: str) -> str:
    result = (
        supabase.table("agent_decisions")
        .select("reasoning")
        .eq("parcel_id", parcel_id)
        .order("decided_at", desc=True)
        .limit(1)
        .execute()
    )
    return result.data[0]["reasoning"] if result.data else ""


def run_tests():
    print("=== LandFinder Sprint 3 Tests ===\n")

    supabase = get_client()

    # Get seed parcel
    result = supabase.table("parcels").select("*").eq("mls_id", "MLS123456").execute()
    assert result.data, "Seed parcel MLS123456 not found — run setup.sql first"
    parcel = result.data[0]
    parcel_id = parcel["id"]
    print(f"Seed parcel ID: {parcel_id}\n")

    # ── SCENARIO A: No touchpoints ───────────────────────────────────────────
    print("--- SCENARIO A: No touchpoints ---")

    supabase.table("touchpoints").delete().eq("parcel_id", parcel_id).execute()

    action = agent_decide(parcel_id, "steven_christie")
    reasoning = get_latest_reasoning(supabase, parcel_id)

    print(f"action:    {action}")
    print(f"reasoning: {reasoning}")
    assert action == "send_initial_outreach", (
        f"Expected 'send_initial_outreach', got '{action}'"
    )
    print("PASS\n")

    # ── SCENARIO B: 2 touchpoints, 5 days ago (within cadence = 28 days) ────
    print("--- SCENARIO B: 2 touchpoints, 5 days ago (within cadence) ---")

    five_days_ago = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()

    supabase.table("touchpoints").insert([
        {
            "parcel_id": parcel_id,
            "channel": "mail",
            "content": "Test letter 1",
            "sent_at": five_days_ago,
            "response_received": False,
            "touch_number": 1,
        },
        {
            "parcel_id": parcel_id,
            "channel": "email",
            "content": "Test email 1",
            "sent_at": five_days_ago,
            "response_received": False,
            "touch_number": 2,
        },
    ]).execute()

    action = agent_decide(parcel_id, "steven_christie")
    reasoning = get_latest_reasoning(supabase, parcel_id)

    print(f"action:    {action}")
    print(f"reasoning: {reasoning}")
    assert action == "wait", f"Expected 'wait', got '{action}'"
    print("PASS\n")

    # ── SCENARIO C: Same touchpoints, 35 days ago (past cadence) ────────────
    print("--- SCENARIO C: 2 touchpoints, 35 days ago (past cadence) ---")

    thirty_five_days_ago = (datetime.now(timezone.utc) - timedelta(days=35)).isoformat()

    supabase.table("touchpoints").update(
        {"sent_at": thirty_five_days_ago}
    ).eq("parcel_id", parcel_id).execute()

    action = agent_decide(parcel_id, "steven_christie")
    reasoning = get_latest_reasoning(supabase, parcel_id)

    print(f"action:    {action}")
    print(f"reasoning: {reasoning}")
    assert action == "send_monthly_retouch", (
        f"Expected 'send_monthly_retouch', got '{action}'"
    )
    print("PASS\n")

    # ── All agent_decisions for this parcel ──────────────────────────────────
    print("--- All agent_decisions for seed parcel ---")
    all_decisions = (
        supabase.table("agent_decisions")
        .select("*")
        .eq("parcel_id", parcel_id)
        .order("decided_at", desc=False)
        .execute()
    )
    for d in all_decisions.data:
        print(f"  action: {d['action']} | decided_at: {d['decided_at']}")
        print(f"  reasoning: {d['reasoning']}\n")

    print("Sprint 3 test complete")


if __name__ == "__main__":
    run_tests()
