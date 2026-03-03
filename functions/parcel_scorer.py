import json
import logging
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import anthropic
from functions.db import get_client

logger = logging.getLogger(__name__)

_ERROR_RESULT = {"score": 50, "tier": "medium", "reasoning": "Scoring error — defaulting to medium"}

SYSTEM_PROMPT = """\
Score this vacant land parcel from 0 to 100 based on owner motivation signals.
Respond ONLY with a valid JSON object with three keys:
score: integer 0-100
tier: one of [high, medium, low]
reasoning: two to three sentences explaining the score

Scoring guidelines:
- Out of state owner address: +20 points (absentee owners are more likely to sell)
- Owner mailing address different from property address: +15 points (owner does not live on the land)
- Lot size between 2 and 25 acres: +15 points (sweet spot for Chester County buyers)
- List price below $500,000: +10 points (more accessible to buyers)
- Days on market over 60: +15 points (sitting listing suggests motivated seller)
- Days on market over 180: +25 points (very motivated seller)
- Township in Chester County PA: +10 points (target market confirmed)
- Owner name is an LLC or company: +10 points (companies often more transactional about selling)
- Prior outreach with no response after 3+ touches: -20 points (low engagement, deprioritize)
- Owner has responded previously: +30 points (engaged owner, high priority)
- Missing owner contact info (no email, no phone): -10 points (harder to reach via all channels)

Tier thresholds: high >= 65, medium 35-64, low < 35\
"""


def score_parcel(parcel_id: str, agent_id: str) -> dict:
    """
    Score a parcel 0-100 for owner motivation using Claude.
    Saves opportunity_score, score_reasoning, and scored_at to Supabase.
    Returns {score, tier, reasoning}.
    """
    supabase = get_client()

    # a. Read full parcel row
    parcel_result = supabase.table("parcels").select("*").eq("id", parcel_id).execute()
    if not parcel_result.data:
        logger.error(f"Parcel {parcel_id} not found.")
        return _ERROR_RESULT
    parcel = parcel_result.data[0]

    # b. Read agent_config (used for future extensibility; validates agent exists)
    config_result = (
        supabase.table("agent_configs").select("*").eq("agent_id", agent_id).execute()
    )
    if not config_result.data:
        logger.error(f"Agent config '{agent_id}' not found.")
        return _ERROR_RESULT

    # c. Read all prior touchpoints
    touch_result = (
        supabase.table("touchpoints")
        .select("response_received")
        .eq("parcel_id", parcel_id)
        .execute()
    )
    touchpoints = touch_result.data or []
    total_touches = len(touchpoints)

    # d. Check response history
    any_response = any(tp.get("response_received") for tp in touchpoints)

    # f. Build user prompt
    email_available = "yes" if parcel.get("owner_email") else "no"
    phone_available = "yes" if parcel.get("owner_phone") else "no"

    user_prompt = (
        "Parcel:\n"
        f"  address: {parcel.get('address')}, {parcel.get('city')}, "
        f"{parcel.get('state')} {parcel.get('zip')}\n"
        f"  county: {parcel.get('county')}\n"
        f"  township: {parcel.get('township')}\n"
        f"  lot_size_acres: {parcel.get('lot_size_acres')}\n"
        f"  list_price: {parcel.get('list_price')}\n"
        f"  days_on_market: {parcel.get('days_on_market')}\n\n"
        "Owner:\n"
        f"  name: {parcel.get('owner_name')}\n"
        f"  mailing_address: {parcel.get('owner_mailing_address')}\n"
        f"  email available: {email_available}\n"
        f"  phone available: {phone_available}\n\n"
        "Touch history:\n"
        f"  total prior touches: {total_touches}\n"
        f"  any prior responses: {'yes' if any_response else 'no'}"
    )

    # g. Call Anthropic API
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY is not set.")

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw_response = message.content[0].text
    logger.info(f"Scoring response for parcel {parcel_id}: {raw_response}")

    # h. Parse JSON — strip markdown fences if present
    try:
        cleaned = raw_response.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            cleaned = "\n".join(lines[1:-1])
        parsed = json.loads(cleaned)
        score = int(parsed.get("score", 50))
        tier = parsed.get("tier", "medium")
        reasoning = parsed.get("reasoning", "")
    except (json.JSONDecodeError, ValueError):
        logger.error(f"JSON parse failed. Raw response: {raw_response}")
        return _ERROR_RESULT

    # i. Update parcel record in Supabase
    supabase.table("parcels").update({
        "opportunity_score": score,
        "score_reasoning": reasoning,
        "scored_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", parcel_id).execute()

    logger.info(f"Parcel {parcel_id} scored: {score}/100 ({tier})")

    # j. Return dict
    return {"score": score, "tier": tier, "reasoning": reasoning}
