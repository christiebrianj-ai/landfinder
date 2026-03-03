import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import anthropic
from functions.db import get_client

logger = logging.getLogger(__name__)

_NOT_ENOUGH_DATA = {"insight": "Not enough data yet — need at least 20 sends to draw conclusions"}


# ─────────────────────────────────────────────────────────────────────────────
# FUNCTION A — Record a response from an owner
# ─────────────────────────────────────────────────────────────────────────────

def record_response(parcel_id: str, channel: str, response_notes: str = "") -> dict:
    """
    Mark the most recent touchpoint for this parcel+channel as responded.
    Updates parcel status to 'escalated'.
    Returns the updated touchpoint row, or None if no touchpoint found.
    """
    supabase = get_client()

    # Find most recent touchpoint for this parcel + channel
    result = (
        supabase.table("touchpoints")
        .select("*")
        .eq("parcel_id", parcel_id)
        .eq("channel", channel)
        .order("sent_at", desc=True)
        .limit(1)
        .execute()
    )

    if not result.data:
        logger.warning(f"No touchpoint found for parcel {parcel_id} via {channel}")
        return None

    tp_id = result.data[0]["id"]

    # Update both responded (A/B tracking) and response_received (legacy) fields
    supabase.table("touchpoints").update({
        "responded": True,
        "response_received": True,
        "response_notes": response_notes,
    }).eq("id", tp_id).execute()

    # Update parcel status
    supabase.table("parcels").update({"status": "escalated"}).eq("id", parcel_id).execute()

    logger.info(f"Response recorded for {parcel_id} via {channel}")

    # Return the updated row
    updated = supabase.table("touchpoints").select("*").eq("id", tp_id).execute()
    return updated.data[0] if updated.data else None


# ─────────────────────────────────────────────────────────────────────────────
# FUNCTION B — A/B performance summary
# ─────────────────────────────────────────────────────────────────────────────

def get_ab_performance(agent_id: str) -> dict:
    """
    Calculate A/B response rates across all touchpoints for this agent's parcels.

    Returns a dict with version_a, version_b stats, winning_version, and insight.
    Returns _NOT_ENOUGH_DATA if fewer than 20 total sends.
    """
    supabase = get_client()

    # Get all parcel IDs for this agent
    parcel_result = (
        supabase.table("parcels").select("id").eq("agent_id", agent_id).execute()
    )
    if not parcel_result.data:
        return _NOT_ENOUGH_DATA

    parcel_ids = [p["id"] for p in parcel_result.data]

    # Get all touchpoints for these parcels
    touch_result = (
        supabase.table("touchpoints")
        .select("*")
        .in_("parcel_id", parcel_ids)
        .execute()
    )
    touchpoints = touch_result.data or []

    if len(touchpoints) < 20:
        return _NOT_ENOUGH_DATA

    # Get all letters for hook_type lookup — keyed by (parcel_id, version)
    letter_result = (
        supabase.table("letters")
        .select("parcel_id, version, hook_type")
        .in_("parcel_id", parcel_ids)
        .execute()
    )
    hook_map = {}
    for letter in (letter_result.data or []):
        key = (letter["parcel_id"], letter.get("version", "A"))
        hook_map[key] = letter.get("hook_type", "")

    # Tally stats per version
    stats = {
        "A": {"sent": 0, "responded": 0, "hook_responses": {}},
        "B": {"sent": 0, "responded": 0, "hook_responses": {}},
    }

    for tp in touchpoints:
        v = tp.get("version") or "A"
        if v not in stats:
            stats[v] = {"sent": 0, "responded": 0, "hook_responses": {}}
        stats[v]["sent"] += 1
        if tp.get("responded"):
            stats[v]["responded"] += 1
            hook = hook_map.get((tp["parcel_id"], v), "unknown")
            stats[v]["hook_responses"][hook] = (
                stats[v]["hook_responses"].get(hook, 0) + 1
            )

    def _top_hook(hook_responses: dict) -> str:
        return max(hook_responses, key=hook_responses.get) if hook_responses else "N/A"

    def _rate(sent: int, responded: int) -> float:
        return round(responded / sent * 100, 1) if sent > 0 else 0.0

    rate_a = _rate(stats["A"]["sent"], stats["A"]["responded"])
    rate_b = _rate(stats["B"]["sent"], stats["B"]["responded"])
    winning = "A" if rate_a >= rate_b else "B"
    winning_rate = max(rate_a, rate_b)

    return {
        "version_a": {
            "total_sent": stats["A"]["sent"],
            "total_responded": stats["A"]["responded"],
            "response_rate": rate_a,
            "top_hook_type": _top_hook(stats["A"]["hook_responses"]),
        },
        "version_b": {
            "total_sent": stats["B"]["sent"],
            "total_responded": stats["B"]["responded"],
            "response_rate": rate_b,
            "top_hook_type": _top_hook(stats["B"]["hook_responses"]),
        },
        "winning_version": winning,
        "insight": (
            f"Version {winning} is outperforming with a {winning_rate}% response rate. "
            f"Top hook: {_top_hook(stats[winning]['hook_responses'])}."
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
# FUNCTION C — AI optimization suggestions
# ─────────────────────────────────────────────────────────────────────────────

def get_optimization_suggestions(agent_id: str) -> str:
    """
    Use Claude to generate 3 actionable suggestions based on A/B performance data.
    Returns a plain text string with suggestions, or a not-enough-data message.
    """
    performance = get_ab_performance(agent_id)

    if "version_a" not in performance:
        return performance.get("insight", "Not enough data.")

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY is not set.")

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        messages=[{
            "role": "user",
            "content": (
                "Based on this A/B performance data for a real estate land prospecting campaign, "
                "provide 3 specific suggestions for improving response rates. Consider: which "
                "version is winning, which hook type is performing best, and what this tells us "
                "about what motivates these land owners to respond. Be specific and actionable.\n\n"
                f"Performance data:\n{json.dumps(performance, indent=2)}"
            ),
        }],
    )

    return message.content[0].text.strip()
