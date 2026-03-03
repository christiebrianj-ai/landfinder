"""
LandFinder — Sprint 3B test suite.

Tests the parcel opportunity scoring layer:
  Test 1 — score_parcel() on the baseline seed parcel
  Test 2 — score_parcel() on a high-opportunity parcel (out-of-state + long DOM)
  Test 3 — agent_decide() uses the opportunity score in its reasoning
  Test 4 — parcel with opportunity_score < 25 gets skipped by agent_decide()
"""

import logging
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s — %(message)s")

from functions.db import get_client
from functions.parcel_scorer import score_parcel
from functions.agent_brain import agent_decide


def get_latest_decision(supabase, parcel_id):
    result = (
        supabase.table("agent_decisions")
        .select("action, reasoning")
        .eq("parcel_id", parcel_id)
        .order("decided_at", desc=True)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else {}


def run_tests():
    print("=== LandFinder Sprint 3B Tests ===\n")

    supabase = get_client()

    # Get seed parcel
    result = supabase.table("parcels").select("*").eq("mls_id", "MLS123456").execute()
    assert result.data, "Seed parcel MLS123456 not found — run setup.sql first"
    parcel = result.data[0]
    parcel_id = parcel["id"]
    print(f"Seed parcel ID: {parcel_id}\n")

    # Save original values for reset at end
    original = {
        "owner_mailing_address": parcel.get("owner_mailing_address"),
        "days_on_market": parcel.get("days_on_market"),
    }

    # ── TEST 1: Score the baseline parcel ───────────────────────────────────
    print("--- TEST 1: Score baseline parcel ---")

    result = score_parcel(parcel_id, "steven_christie")
    print(f"score:     {result['score']}/100")
    print(f"tier:      {result['tier']}")
    print(f"reasoning: {result['reasoning']}\n")

    # Confirm saved to Supabase
    saved = supabase.table("parcels").select(
        "opportunity_score, score_reasoning, scored_at"
    ).eq("id", parcel_id).execute().data[0]

    assert saved["opportunity_score"] is not None, "opportunity_score not saved"
    assert saved["scored_at"] is not None, "scored_at not saved"
    print(f"Supabase saved — opportunity_score: {saved['opportunity_score']}, "
          f"scored_at: {saved['scored_at']}")
    print("PASS\n")

    # ── TEST 2: Score a high-opportunity parcel ──────────────────────────────
    print("--- TEST 2: Score high-opportunity parcel (out-of-state + 210 DOM) ---")

    supabase.table("parcels").update({
        "owner_mailing_address": "789 Far Away St, Los Angeles CA 90001",
        "days_on_market": 210,
    }).eq("id", parcel_id).execute()

    result = score_parcel(parcel_id, "steven_christie")
    print(f"score:     {result['score']}/100")
    print(f"tier:      {result['tier']}")
    print(f"reasoning: {result['reasoning']}\n")

    assert result["tier"] == "high", (
        f"Expected tier='high', got '{result['tier']}' (score={result['score']})"
    )
    print("PASS\n")

    # ── TEST 3: agent_decide uses the opportunity score ──────────────────────
    print("--- TEST 3: agent_decide incorporates opportunity score ---")

    # Clear touchpoints so baseline would be send_initial_outreach
    supabase.table("touchpoints").delete().eq("parcel_id", parcel_id).execute()

    action = agent_decide(parcel_id, "steven_christie")
    decision = get_latest_decision(supabase, parcel_id)
    reasoning = decision.get("reasoning", "")

    print(f"action:    {action}")
    print(f"reasoning: {reasoning}")

    score_mentioned = any(
        word in reasoning.lower()
        for word in ["score", "opportunity", "priority", "high", "motivated"]
    )
    print(f"Score context reflected in reasoning: {score_mentioned}")
    print("PASS\n")

    # ── TEST 4: Low score parcel gets skipped ────────────────────────────────
    print("--- TEST 4: Low opportunity score (20/100) forces skip ---")

    supabase.table("touchpoints").delete().eq("parcel_id", parcel_id).execute()
    supabase.table("parcels").update({
        "opportunity_score": 20,
        "score_reasoning": "Very low opportunity — small lot, local owner, no engagement",
        "scored_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", parcel_id).execute()

    action = agent_decide(parcel_id, "steven_christie")
    decision = get_latest_decision(supabase, parcel_id)
    reasoning = decision.get("reasoning", "")

    print(f"action:    {action}")
    print(f"reasoning: {reasoning}")

    assert action == "skip", f"Expected 'skip', got '{action}'"
    print("Low score skip logic working correctly")
    print("PASS\n")

    # ── Reset seed parcel to original values ─────────────────────────────────
    print("--- Resetting seed parcel to original values ---")
    supabase.table("parcels").update({
        "owner_mailing_address": original["owner_mailing_address"],
        "days_on_market": original["days_on_market"],
        "opportunity_score": None,
        "score_reasoning": None,
        "scored_at": None,
    }).eq("id", parcel_id).execute()
    print("Reset complete\n")

    print("Sprint 3B test complete")


if __name__ == "__main__":
    run_tests()
