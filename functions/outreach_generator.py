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

# ─────────────────────────────────────────────────────────────────────────────
# Style reference — Steven Christie's three sample letters
# ─────────────────────────────────────────────────────────────────────────────

SAMPLE_LETTERS = """\
=== SAMPLE LETTER 1 (buyer hook, couple, first touch) ===

February 20, 2026

Jennifer & Scott Boorse
679 Brintons Bridge Rd
West Chester PA 19382

Dear Jennifer & Scott,

I am currently working with a client who is actively looking for vacant building lots in Birmingham
Township. I noticed that you own 2.1 Acres at 677 Brinton Bridge Rd, and I wanted to see if you
might have any interest in selling now or in the near future

My client is a qualified buyer, highly motivated and ready to move forward if the right opportunity
arises. If you have considered selling now or the near future, please feel free to call, text, or email
me at your earliest convenience.

Looking forward to hearing from you!

Sincerely,
Steven Christie
Keller Williams Real Estate
610-389-2810 Cell
610-436-6500 Office
stevenchristie4@gmail.com

P.S. Even if you are not actively looking to sell, I'm happy to share current land values and buyer
activity in your area if helpful.

Steven Christie
A Trusted Name In Real Estate.
300 Willowbrook Lane, Suite 310, West Chester, PA 19382
A member of the franchise system of Keller Williams

=== SAMPLE LETTER 2 (buyer hook, single owner, first touch) ===

February 20, 2026

Jorge Paredes
223 E Street Rd
Kennett Square PA 19348

Dear Jorge,

I am currently working with a client who is actively looking for vacant building lots in East
Marlborough Township. I noticed that you own 3.8 Acres at 219 E Street Rd, and I wanted to see if
you might have any interest in selling now or in the near future

My client is a qualified buyer, highly motivated and ready to move forward if the right opportunity
arises. If you have considered selling now or the near future, please feel free to call, text, or email
me at your earliest convenience.

Looking forward to hearing from you!

Sincerely,
Steven Christie
Keller Williams Real Estate
610-389-2810 Cell
610-436-6500 Office
stevenchristie4@gmail.com

P.S. Even if you are not actively looking to sell, I'm happy to share current land values and buyer
activity in your area if helpful.

Steven Christie
A Trusted Name In Real Estate.
300 Willowbrook Lane, Suite 310, West Chester, PA 19382
A member of the franchise system of Keller Williams

=== SAMPLE LETTER 3 (local intelligence hook, single owner, first touch) ===

February 20, 2026

Ryan Shrum
1483 S Keim St
Pottstown PA 19465

Dear Ryan,

I noticed on the Chester County Planning Commission report that you are subdividing your
property at 1871 Young Road in South Coventry Township.

I am working with a client who has interest if you are planning to sell the lots.

If you have any interest in selling now or the near future please contact me at your convenience.

Sincerely,
Steven Christie
Keller Williams Real Estate
610-389-2810 Cell
610-436-6500 Office
stevenchristie4@gmail.com

Steven Christie
A Trusted Name In Real Estate.
300 Willowbrook Lane, Suite 310, West Chester, PA 19382
A member of the franchise system of Keller Williams\
"""

# ─────────────────────────────────────────────────────────────────────────────
# Hook type definitions
# ─────────────────────────────────────────────────────────────────────────────

HOOK_TYPES = {
    "A": "buyer_angle",
    "B": "market_activity_angle",
}

HOOK_DESCRIPTIONS = {
    "buyer_angle": (
        "BUYER ANGLE: Open by mentioning an active, qualified buyer who is specifically "
        "looking for vacant land in this township right now. Emphasize the buyer's urgency "
        "and readiness to move. This is your primary hook — lead with this buyer opportunity."
    ),
    "market_activity_angle": (
        "MARKET ACTIVITY ANGLE: Open by referencing current land market conditions and "
        "values in the area. The owner may not realize what their parcel is worth right now. "
        "Position Steven as someone with local market intelligence who can share that insight "
        "whether or not they want to sell. Do not lead with a buyer."
    ),
}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _auto_assign_version(parcel_id: str, touch_number: int, prev_version: str = None) -> str:
    """
    Deterministically assign A/B version.
    touch_number == 1: last hex digit of UUID, 0-4 → A, 5-9/a-f → B.
    touch_number > 1: alternate from prev_version.
    """
    if touch_number > 1 and prev_version:
        return "B" if prev_version == "A" else "A"
    last_char = parcel_id[-1].lower()
    return "A" if last_char in "01234" else "B"


def _owner_salutation(owner_name: str) -> str:
    """Return the salutation string for a given owner name."""
    if not owner_name:
        return "Dear Sir or Madam"
    name_lower = owner_name.lower()
    company_flags = ["llc", "inc", "corp", "ltd", "holding", "holdings",
                     "trust", "properties", "company", "associates", "partners"]
    if any(flag in name_lower for flag in company_flags):
        return f"To the attention of {owner_name}"
    # Couples: "George & Martha Williams" → "Dear George & Martha"
    if "&" in owner_name or " and " in owner_name.lower():
        parts = owner_name.split()
        given = " ".join(parts[:-1])   # everything except assumed last name
        return f"Dear {given}"
    # Single person: first word only
    return f"Dear {owner_name.split()[0]}"


def _is_company(owner_name: str) -> bool:
    if not owner_name:
        return False
    name_lower = owner_name.lower()
    company_flags = ["llc", "inc", "corp", "ltd", "holding", "holdings",
                     "trust", "properties", "company", "associates", "partners"]
    return any(flag in name_lower for flag in company_flags)


def _build_system_prompt(channel: str, hook_type: str, touch_number: int) -> str:
    today = datetime.now().strftime("%B %d, %Y")
    hook_desc = HOOK_DESCRIPTIONS[hook_type]

    if channel == "mail":
        channel_instructions = (
            f"Write a complete physical mail letter.\n"
            f"- Today's date line: {today}\n"
            "- Owner name and mailing address block (2–3 lines)\n"
            "- Salutation line (provided in user prompt)\n"
            "- 2–3 short body paragraphs\n"
            "- 'Sincerely,' closing\n"
            "- Full signature block:\n"
            "    Steven Christie\n"
            "    Keller Williams Real Estate\n"
            "    610-389-2810 Cell\n"
            "    610-436-6500 Office\n"
            "    stevenchristie4@gmail.com\n"
            "- A P.S. line (always include): offer to share current land values "
            "even if they are not actively looking to sell.\n"
            "- Footer:\n"
            "    Steven Christie\n"
            "    A Trusted Name In Real Estate.\n"
            "    300 Willowbrook Lane, Suite 310, West Chester, PA 19382\n"
            "    A member of the franchise system of Keller Williams"
        )
    elif channel == "email":
        channel_instructions = (
            "Write a shorter email. Format your entire response EXACTLY as:\n\n"
            "SUBJECT: {your subject line here}\n"
            "BODY: {your email body here}\n\n"
            "- Subject: short and specific (under 60 characters)\n"
            "- Body: 2 short paragraphs, same warm voice as the sample letters\n"
            "- End body with full signature block:\n"
            "    Steven Christie\n"
            "    Keller Williams Real Estate\n"
            "    610-389-2810 Cell | 610-436-6500 Office\n"
            "    stevenchristie4@gmail.com\n"
            "    stevenchristierealestate.com\n"
            "- No P.S. line needed for email"
        )
    else:  # sms
        channel_instructions = (
            "Write a single SMS text message.\n"
            "HARD LIMIT: 160 characters MAXIMUM — every letter, space, and punctuation counts.\n"
            "Count your characters before responding. If over 160, shorten it.\n"
            "Good structure (≈130 chars): 'Hi [Name] - [one hook sentence, township]. "
            "Interested in selling? Call Steven: 610-389-2810'\n"
            "- Use owner first name only (e.g. 'George' not 'George & Martha')\n"
            "- Name the township\n"
            "- Include Steven's cell: 610-389-2810\n"
            "- Output ONLY the SMS text — no quotes, no labels, nothing else"
        )

    retouch_note = (
        "" if touch_number == 1 else
        "\n\nIMPORTANT — RETOUCH: Use a completely fresh angle. "
        "Do NOT mention or reference any prior letters or outreach."
    )

    return (
        "You are writing highly personalized real estate outreach letters for "
        "Steven Christie, REALTOR® at Keller Williams Real Estate, West Chester PA.\n\n"
        "Study these three sample letters Steven has written. Match his style exactly: "
        "warm but professional, brief sentences, specific property details, never generic.\n\n"
        f"{SAMPLE_LETTERS}\n\n"
        "━━━ DRAFTING INSTRUCTIONS ━━━\n\n"
        f"Opening hook for this message:\n{hook_desc}\n\n"
        f"Channel: {channel.upper()}\n"
        f"{channel_instructions}\n\n"
        "Content rules (always follow):\n"
        "- Reference the EXACT acreage and EXACT township name in the body\n"
        "- Use the salutation exactly as provided in the user prompt\n"
        "- Never reveal the opportunity score or any internal system data\n"
        "- Sound like Steven wrote it personally — never like a template\n"
        "- Do not include a letterhead or header block at the top of the letter. "
        "Start directly with the date on the first line, followed by the owner "
        "address block, then the salutation. The signature block at the end should "
        "include Steven's full name, brokerage, cell, office, and email — but no "
        "decorative header at the top."
        f"{retouch_note}"
    )


def _build_user_prompt(parcel: dict, owner_name: str, hook_type: str,
                       version: str, touch_number: int) -> str:
    salutation = _owner_salutation(owner_name)
    is_company = _is_company(owner_name)

    company_note = (
        "\nIMPORTANT: This owner is a company/LLC. "
        f"The salutation MUST be: '{salutation}' (not 'Dear ...')"
        if is_company else ""
    )

    return (
        f"Owner name: {owner_name}\n"
        f"Owner mailing address: {parcel.get('owner_mailing_address')}\n"
        f"Property address: {parcel.get('address')}, {parcel.get('city')}, "
        f"{parcel.get('state')} {parcel.get('zip')}\n"
        f"Lot size: {parcel.get('lot_size_acres')} acres\n"
        f"Township: {parcel.get('township')}\n"
        f"County: {parcel.get('county')}\n"
        f"Opportunity score: {parcel.get('opportunity_score', 'N/A')}/100\n"
        f"Score context: {parcel.get('score_reasoning', 'N/A')}\n"
        f"Version: {version} | Hook: {hook_type}\n"
        f"Touch number: {touch_number}\n"
        f"Salutation to use: {salutation}"
        f"{company_note}\n\n"
        "Please draft the outreach message now."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Main function
# ─────────────────────────────────────────────────────────────────────────────

def generate_outreach(parcel_id: str, agent_id: str, channel: str,
                      touch_number: int = 1, version: str = "A") -> dict:
    """
    Generate personalized outreach content for a parcel.

    Args:
        parcel_id:    UUID of the parcel
        agent_id:     e.g. 'steven_christie'
        channel:      'mail', 'email', or 'sms'
        touch_number: 1 for initial, 2+ for retouch
        version:      'A' (buyer angle) or 'B' (market angle).
                      Pass version=_auto_assign_version(...) for production use.

    Returns:
        {channel, version, hook_type, body, subject (email only)}
        or None on failure.
    """
    try:
        supabase = get_client()

        # a. Read parcel
        parcel_result = (
            supabase.table("parcels").select("*").eq("id", parcel_id).execute()
        )
        if not parcel_result.data:
            logger.error(f"Parcel {parcel_id} not found.")
            return None
        parcel = parcel_result.data[0]

        # b. Read agent_config
        config_result = (
            supabase.table("agent_configs")
            .select("*")
            .eq("agent_id", agent_id)
            .execute()
        )
        if not config_result.data:
            logger.error(f"Agent config '{agent_id}' not found.")
            return None

        # c. Prior touchpoints
        touch_result = (
            supabase.table("touchpoints")
            .select("version, responded")
            .eq("parcel_id", parcel_id)
            .execute()
        )
        # d. Any prior responses
        touchpoints = touch_result.data or []

        # d. Determine hook_type from version
        hook_type = HOOK_TYPES.get(version, "buyer_angle")

        # f. Build prompts
        owner_name = parcel.get("owner_name") or "Owner"
        system_prompt = _build_system_prompt(channel, hook_type, touch_number)
        user_prompt = _build_user_prompt(parcel, owner_name, hook_type, version, touch_number)

        # h. Call Anthropic API
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError("ANTHROPIC_API_KEY is not set.")

        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1000,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        raw = message.content[0].text.strip()
        logger.info(f"Raw outreach response ({channel}, v{version}): {raw[:200]}...")

        # i. Parse email subject/body
        subject = None
        body = raw

        if channel == "email":
            if "SUBJECT:" in raw and "BODY:" in raw:
                after_subject = raw.split("SUBJECT:", 1)[1]
                subject_line, body_part = after_subject.split("BODY:", 1)
                subject = subject_line.strip()
                body = body_part.strip()
            else:
                # Fallback: use first line as subject
                lines = raw.splitlines()
                subject = lines[0].strip()
                body = "\n".join(lines[1:]).strip()

        # SMS guard: if over 160 chars, ask Claude to shorten it once
        if channel == "sms" and len(body) > 160:
            logger.warning(f"SMS too long ({len(body)} chars) — requesting shorter version")
            retry = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=200,
                messages=[{
                    "role": "user",
                    "content": (
                        f"This SMS is {len(body)} characters — too long. Rewrite it in "
                        f"160 characters or fewer. Keep the owner first name, township name, "
                        f"and phone number 610-389-2810. Output ONLY the SMS text:\n\n{body}"
                    ),
                }],
            )
            body = retry.content[0].text.strip().strip('"')
            logger.info(f"SMS shortened to {len(body)} chars")

        # j. Insert draft into letters table
        supabase.table("letters").insert({
            "parcel_id": parcel_id,
            "owner_name": owner_name,
            "mailing_address": parcel.get("owner_mailing_address"),
            "letter_body": body,
            "status": "draft",
            "version": version,
            "hook_type": hook_type,
        }).execute()

        logger.info(f"Draft letter saved for parcel {parcel_id} (v{version}, {channel})")

        # k. Return dict
        return {
            "channel": channel,
            "version": version,
            "hook_type": hook_type,
            "subject": subject,
            "body": body,
        }

    except Exception as e:
        logger.error(f"generate_outreach failed: {e}", exc_info=True)
        return None
