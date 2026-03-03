import logging
import os
import sys
from urllib.parse import quote

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from functions.db import get_client

logger = logging.getLogger(__name__)


def get_satellite_image(parcel_id: str):
    """
    Build a Google Maps Static API satellite image URL for a parcel,
    save it to the parcels table, and return it.

    Returns the URL string, or None if the address is missing.
    """
    supabase = get_client()

    result = (
        supabase.table("parcels")
        .select("address, city, state, zip")
        .eq("id", parcel_id)
        .execute()
    )

    if not result.data:
        logger.warning(f"Parcel {parcel_id} not found.")
        return None

    row = result.data[0]
    address = row.get("address")
    city = row.get("city")
    state = row.get("state")
    zip_code = row.get("zip")

    if not address:
        logger.warning(f"Parcel {parcel_id} has no address — skipping satellite image.")
        return None

    full_address = f"{address}, {city}, {state} {zip_code}"
    encoded_address = quote(full_address)

    key = os.environ.get("GOOGLE_MAPS_KEY")
    if not key:
        raise EnvironmentError("GOOGLE_MAPS_KEY is not set.")

    url = (
        "https://maps.googleapis.com/maps/api/staticmap"
        f"?center={encoded_address}&zoom=18&size=600x400&maptype=satellite&key={key}"
    )

    supabase.table("parcels").update({"satellite_image_url": url}).eq("id", parcel_id).execute()
    logger.info(f"Satellite image URL saved for parcel {parcel_id}.")

    return url
