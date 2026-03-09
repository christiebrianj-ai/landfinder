import logging
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

from functions.db import get_client
from functions.outreach_generator import generate_outreach

logger = logging.getLogger(__name__)


def send_email(parcel_id: str, agent_id: str) -> dict:
    """
    Generate and send an email for this parcel via SendGrid.

    Returns:
        {success: True, message_id}         on success
        {success: False, reason/error}      on failure
    """
    try:
        supabase = get_client()

        # a. Generate email content
        outreach = generate_outreach(parcel_id, agent_id, 'email', touch_number=1)
        if not outreach:
            return {'success': False, 'error': 'generate_outreach returned None'}

        subject = outreach.get('subject') or 'Your land in Chester County'
        body = outreach['body']
        version = outreach.get('version', 'A')

        # b. Read parcel for owner_email
        parcel_result = (
            supabase.table('parcels').select('owner_email').eq('id', parcel_id).execute()
        )
        if not parcel_result.data:
            return {'success': False, 'error': f'Parcel {parcel_id} not found'}
        owner_email = parcel_result.data[0].get('owner_email')

        # c. Skip if no email
        if not owner_email:
            logger.info(f'No email address for parcel {parcel_id} — skipping email send')
            return {'success': False, 'reason': 'no_email'}

        # d. From email — from agent_config or default
        config_result = (
            supabase.table('agent_configs')
            .select('sendgrid_from_email')
            .eq('agent_id', agent_id)
            .execute()
        )
        from_email = 'christiebrianj@gmail.com'
        if config_result.data:
            from_email = (
                config_result.data[0].get('sendgrid_from_email') or from_email
            )

        # e-f. Build and send SendGrid message
        api_key = os.environ.get('SENDGRID_API_KEY')
        if not api_key:
            raise EnvironmentError('SENDGRID_API_KEY is not set')

        p = 'font-family:Arial;font-size:12pt;margin:0 0 8pt 0;'
        html_body = (
            '<html><body>'
            + ''.join(
                f'<p style="{p}">{line}</p>' if line.strip() else f'<p style="{p}">&nbsp;</p>'
                for line in body.splitlines()
            )
            + '</body></html>'
        )

        message = Mail(
            from_email=from_email,
            to_emails=owner_email,
            subject=subject,
            plain_text_content=body,
            html_content=html_body,
        )

        sg = SendGridAPIClient(api_key)
        response = sg.send(message)
        message_id = response.headers.get('X-Message-Id', '')

        logger.info(
            f'Email sent for parcel {parcel_id}, status={response.status_code}, '
            f'message_id={message_id}'
        )

        # h. Insert touchpoint
        existing = (
            supabase.table('touchpoints')
            .select('id', count='exact')
            .eq('parcel_id', parcel_id)
            .execute()
        )
        touch_number = (existing.count or 0) + 1

        supabase.table('touchpoints').insert({
            'parcel_id': parcel_id,
            'channel': 'email',
            'content': subject,
            'sent_at': datetime.now(timezone.utc).isoformat(),
            'touch_number': touch_number,
            'version': version,
        }).execute()

        return {'success': True, 'message_id': message_id}

    except Exception as e:
        body = getattr(e, 'body', None)
        logger.error(f'send_email failed: {e} | body: {body}', exc_info=True)
        return {'success': False, 'error': str(e), 'detail': str(body)}
