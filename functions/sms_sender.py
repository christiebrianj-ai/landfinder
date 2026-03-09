import logging
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from twilio.rest import Client

from functions.db import get_client
from functions.outreach_generator import generate_outreach

logger = logging.getLogger(__name__)


def send_sms(parcel_id: str, agent_id: str) -> dict:
    """
    Generate and send an SMS for this parcel via Twilio.

    Returns:
        {success: True, message_sid}        on success
        {success: False, reason/error}      on failure
    """
    try:
        supabase = get_client()

        # a. Read parcel for owner_phone
        parcel_result = (
            supabase.table('parcels').select('owner_phone').eq('id', parcel_id).execute()
        )
        if not parcel_result.data:
            return {'success': False, 'error': f'Parcel {parcel_id} not found'}
        owner_phone = parcel_result.data[0].get('owner_phone')

        # b. Skip if no phone
        if not owner_phone:
            logger.info(f'No phone number for parcel {parcel_id} — skipping SMS send')
            return {'success': False, 'reason': 'no_phone'}

        # c. Generate SMS content
        outreach = generate_outreach(parcel_id, agent_id, 'sms', touch_number=1)
        if not outreach:
            return {'success': False, 'error': 'generate_outreach returned None'}
        sms_body = outreach['body']
        version = outreach.get('version', 'A')

        # d-e. Init Twilio client
        twilio_sid = os.environ.get('TWILIO_SID')
        twilio_token = os.environ.get('TWILIO_TOKEN')
        twilio_phone = os.environ.get('TWILIO_PHONE')
        if not all([twilio_sid, twilio_token, twilio_phone]):
            raise EnvironmentError('TWILIO_SID, TWILIO_TOKEN, and TWILIO_PHONE must all be set')

        client = Client(twilio_sid, twilio_token)

        # f. Send SMS
        message = client.messages.create(
            from_=twilio_phone,
            to=owner_phone,
            body=sms_body,
        )

        logger.info(
            f'SMS sent for parcel {parcel_id}, sid={message.sid}, '
            f'status={message.status}'
        )

        # g. Insert touchpoint
        existing = (
            supabase.table('touchpoints')
            .select('id', count='exact')
            .eq('parcel_id', parcel_id)
            .execute()
        )
        touch_number = (existing.count or 0) + 1

        supabase.table('touchpoints').insert({
            'parcel_id': parcel_id,
            'channel': 'sms',
            'content': sms_body,
            'sent_at': datetime.now(timezone.utc).isoformat(),
            'touch_number': touch_number,
            'version': version,
        }).execute()

        return {'success': True, 'message_sid': message.sid}

    except Exception as e:
        logger.error(f'send_sms failed: {e}', exc_info=True)
        return {'success': False, 'error': str(e)}
