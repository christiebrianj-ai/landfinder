import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from functions.db import get_client

logger = logging.getLogger(__name__)


def enrich_owner(parcel_id: str):
    """
    Attempt to enrich owner contact info for a parcel via skip tracing.

    If owner_email and owner_phone are already populated, returns the existing
    values without making any external API call (avoids duplicate charges).

    Returns a dict with owner_email and owner_phone if already populated,
    or None if skip tracing would be needed but is not yet configured.
    """
    supabase = get_client()

    result = (
        supabase.table("parcels")
        .select("owner_name, owner_mailing_address, owner_email, owner_phone")
        .eq("id", parcel_id)
        .execute()
    )

    if not result.data:
        logger.warning(f"Parcel {parcel_id} not found.")
        return None

    row = result.data[0]
    owner_email = row.get("owner_email")
    owner_phone = row.get("owner_phone")

    if owner_email and owner_phone:
        logger.info(
            f"Owner contact already populated for parcel {parcel_id} — skipping API call."
        )
        return {"owner_email": owner_email, "owner_phone": owner_phone}

    # TODO: Replace this with PropStream or BatchLeads API call
    logger.info(
        "Skip tracing not yet configured — owner contact info will need to be "
        "populated manually or via PropStream"
    )
    return None
