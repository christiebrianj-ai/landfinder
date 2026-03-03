import json
import logging
import os
import sys
from datetime import datetime, timezone

from dateutil.parser import parse as parse_dt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import anthropic
from functions.db import get_client

logger = logging.getLogger(__name__)


def agent_decide(parcel_id: str, agent_id: str) -> str:
    """
    Core reasoning function. Reads parcel, agent config, and touch history
    from Supabase, calls Claude to decide the next action, logs the decision,
    and returns the action string.

    Possible actions:
      send_initial_outreach, send_monthly_retouch, wait,
      escalate_to_agent, skip
    """
    supabase = get_client()

    # a. Read full parcel row
    parcel_result = supabase.table("parcels").select("*").eq("id", parcel_id).execute()
    if not parcel_result.data:
        logger.error(f"Parcel {parcel_id} not found.")
        return "wait"
    parcel = parcel_result.data[0]

    # b. Read agent_config row
    config_result = (
        supabase.table("agent_configs").select("*").eq("agent_id", agent_id).execute()
    )
    if not config_result.data:
        logger.error(f"Agent config '{agent_id}' not found.")
        return "wait"
    config = config_result.data[0]

    # c. Read ALL touchpoints for this parcel, ordered by sent_at ASC
    touch_result = (
        supabase.table("touchpoints")
        .select("*")
        .eq("parcel_id", parcel_id)
        .order("sent_at", desc=False)
        .execute()
    )
    touchpoints = touch_result.data or []

    # d. Read most recent agent_decision for this parcel
    decision_result = (
        supabase.table("agent_decisions")
        .select("*")
        .eq("parcel_id", parcel_id)
        .order("decided_at", desc=True)
        .limit(1)
        .execute()
    )
    # (available for future use / audit)
    last_decision = decision_result.data[0] if decision_result.data else None

    # e. Calculate days_since_last_contact
    if touchpoints:
        last_sent_str = touchpoints[-1]["sent_at"]
        last_sent = parse_dt(last_sent_str)
        now = datetime.now(timezone.utc)
        days_since_last_contact = (now - last_sent).days
    else:
        days_since_last_contact = 999

    # f. Count total touches
    total_touches = len(touchpoints)

    # g. System prompt
    agent_name = config.get("agent_name", agent_id)
    brokerage = config.get("brokerage", "")
    retouch_cadence_days = config.get("retouch_cadence_days", 28)

    system_prompt = (
        f"You are an AI agent managing land prospecting for {agent_name}, a real estate "
        f"agent at {brokerage}. Your goal is to identify vacant land owners who might "
        f"want to sell and get them to respond to outreach.\n\n"
        "Review the parcel and owner information below and decide what action to take.\n"
        "Respond ONLY with a valid JSON object with two keys:\n"
        "action: one of [send_initial_outreach, send_monthly_retouch, wait, "
        "escalate_to_agent, skip]\n"
        "reasoning: one sentence explaining your decision\n\n"
        "Decision rules:\n"
        "- send_initial_outreach: no prior touchpoints exist\n"
        "- send_monthly_retouch: has touchpoints, no response, days_since_last_contact "
        ">= retouch_cadence_days, total_touches < 6\n"
        "- wait: has touchpoints, no response, days_since_last_contact < retouch_cadence_days\n"
        "- escalate_to_agent: owner has responded (response_received = true on any touchpoint)\n"
        "- skip: total_touches >= 6 with no response"
    )

    # h. User prompt
    touch_lines = []
    for tp in touchpoints:
        touch_lines.append(
            f"  - channel: {tp.get('channel')}, "
            f"sent_at: {tp.get('sent_at')}, "
            f"response_received: {tp.get('response_received')}"
        )
    touch_history = "\n".join(touch_lines) if touch_lines else "  (none)"

    email_available = "yes" if parcel.get("owner_email") else "no"
    phone_available = "yes" if parcel.get("owner_phone") else "no"

    user_prompt = (
        "Parcel:\n"
        f"  address: {parcel.get('address')}, {parcel.get('city')}, "
        f"{parcel.get('state')} {parcel.get('zip')}\n"
        f"  township: {parcel.get('township')}\n"
        f"  county: {parcel.get('county')}\n"
        f"  lot_size_acres: {parcel.get('lot_size_acres')}\n"
        f"  list_price: {parcel.get('list_price')}\n"
        f"  days_on_market: {parcel.get('days_on_market')}\n\n"
        "Owner:\n"
        f"  name: {parcel.get('owner_name')}\n"
        f"  email available: {email_available}\n"
        f"  phone available: {phone_available}\n\n"
        f"Touch history:\n{touch_history}\n\n"
        f"Days since last contact: {days_since_last_contact}\n"
        f"Total touches: {total_touches}\n"
        f"Retouch cadence: {retouch_cadence_days} days"
    )

    # i. Call Anthropic API
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY is not set.")

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw_response = message.content[0].text
    logger.info(f"Anthropic raw response: {raw_response}")

    # j. Parse JSON — strip markdown fences if the model wrapped its output
    try:
        cleaned = raw_response.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            cleaned = "\n".join(lines[1:-1])
        parsed = json.loads(cleaned)
        action = parsed.get("action", "wait")
        reasoning = parsed.get("reasoning", "")
    except json.JSONDecodeError:
        logger.error(f"JSON parse failed. Raw response: {raw_response}")
        action = "wait"
        reasoning = "JSON parse error — defaulting to wait"

    # k. Insert into agent_decisions
    supabase.table("agent_decisions").insert(
        {"parcel_id": parcel_id, "action": action, "reasoning": reasoning}
    ).execute()

    logger.info(f"Decision for parcel {parcel_id}: {action} — {reasoning}")

    # l. Return action
    return action
