import logging
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from functions.db import get_client
from functions.agent_brain import agent_decide
from functions.mail_sender import send_letter
from functions.email_sender import send_email
from functions.sms_sender import send_sms

logger = logging.getLogger(__name__)

SEND_ACTIONS = {'send_initial_outreach', 'send_monthly_retouch'}


def coordinate_outreach(parcel_id: str, agent_id: str) -> dict:
    """
    Master function that runs agent_decide and, if approved, sends all
    three channels (mail, email, SMS) for the given parcel.

    Each channel is attempted independently — one failure never blocks others.

    Returns:
        {
            parcel_id,
            sent: True/False,
            reason: action if not sent,
            mail: result dict,
            email: result dict,
            sms: result dict,
            channels_sent: int,
            timestamp: ISO string,
        }
    """
    try:
        supabase = get_client()

        # a. Confirm parcel and agent exist
        parcel_result = (
            supabase.table('parcels').select('id').eq('id', parcel_id).execute()
        )
        if not parcel_result.data:
            logger.error(f'Parcel {parcel_id} not found')
            return {'parcel_id': parcel_id, 'sent': False, 'reason': 'parcel_not_found'}

        # b. Ask agent_decide whether to send
        action = agent_decide(parcel_id, agent_id)
        logger.info(f'agent_decide returned: {action} for parcel {parcel_id}')

        if action not in SEND_ACTIONS:
            logger.info(f'Outreach skipped — action={action}')
            return {
                'parcel_id': parcel_id,
                'sent': False,
                'reason': action,
                'timestamp': datetime.now(timezone.utc).isoformat(),
            }

        # c. Send all channels independently
        logger.info(f'Sending all channels for parcel {parcel_id}')

        mail_result = send_letter(parcel_id, agent_id)
        logger.info(f'Mail result: {mail_result}')

        email_result = send_email(parcel_id, agent_id)
        logger.info(f'Email result: {email_result}')

        sms_result = send_sms(parcel_id, agent_id)
        logger.info(f'SMS result: {sms_result}')

        channels_sent = sum([
            1 if mail_result.get('success') else 0,
            1 if email_result.get('success') else 0,
            1 if sms_result.get('success') else 0,
        ])

        # d. Return summary
        return {
            'parcel_id': parcel_id,
            'sent': True,
            'action': action,
            'mail': mail_result,
            'email': email_result,
            'sms': sms_result,
            'channels_sent': channels_sent,
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f'coordinate_outreach failed: {e}', exc_info=True)
        return {
            'parcel_id': parcel_id,
            'sent': False,
            'error': str(e),
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }
