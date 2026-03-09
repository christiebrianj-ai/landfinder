import logging
import os
import sys
from datetime import datetime, timezone, date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import lob_python
from lob_python.api import letters_api
from lob_python.model.address_editable import AddressEditable
from lob_python.model.letter_editable import LetterEditable
from lob_python.model.ltr_use_type import LtrUseType

from functions.db import get_client

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _parse_mailing_address(address_str: str):
    """
    Parse '456 Owner Lane, Philadelphia PA 19103' into
    (address_line1, city, state, zip_code).
    """
    if not address_str:
        return '', '', '', ''
    parts = address_str.rsplit(',', 1)
    address_line1 = parts[0].strip()
    city = state = zip_code = ''
    if len(parts) > 1:
        tokens = parts[1].strip().split()
        if len(tokens) >= 3:
            zip_code = tokens[-1]
            state = tokens[-2]
            city = ' '.join(tokens[:-2])
        elif len(tokens) == 2:
            state = tokens[-1]
            city = tokens[0]
        elif len(tokens) == 1:
            city = tokens[0]
    return address_line1, city, state, zip_code


def _body_to_html(body: str) -> str:
    """Wrap plain-text letter body in minimal HTML for Lob rendering."""
    p = 'font-family:Arial;font-size:12pt;margin:0 0 6pt 0;'
    safe = (body
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;'))
    paragraphs = safe.replace('\n', f'</p><p style="{p}">')
    return f'<html><body><p style="{p}">{paragraphs}</p></body></html>'


# ─────────────────────────────────────────────────────────────────────────────
# Main function
# ─────────────────────────────────────────────────────────────────────────────

def send_letter(parcel_id: str, agent_id: str) -> dict:
    """
    Send the most recent draft letter for this parcel via Lob (test mode).

    Returns:
        {success: True, lob_letter_id, send_date}  on success
        {success: False, error: message}            on failure
    """
    try:
        supabase = get_client()

        # a. Most recent draft letter for this parcel
        letter_result = (
            supabase.table('letters')
            .select('*')
            .eq('parcel_id', parcel_id)
            .eq('status', 'draft')
            .order('created_at', desc=True)
            .limit(1)
            .execute()
        )
        if not letter_result.data:
            logger.error(f'No draft letter found for parcel {parcel_id}')
            return {'success': False, 'error': 'No draft letter found'}
        letter = letter_result.data[0]
        letter_id = letter['id']

        # b. Parcel row
        parcel_result = (
            supabase.table('parcels').select('*').eq('id', parcel_id).execute()
        )
        if not parcel_result.data:
            return {'success': False, 'error': f'Parcel {parcel_id} not found'}
        parcel = parcel_result.data[0]

        # c. Agent config — return address
        config_result = (
            supabase.table('agent_configs')
            .select('*')
            .eq('agent_id', agent_id)
            .execute()
        )
        if not config_result.data:
            return {'success': False, 'error': f'Agent config {agent_id} not found'}
        agent = config_result.data[0]

        # d. Init Lob client
        api_key = os.environ.get('LOB_TEST_KEY')
        if not api_key:
            raise EnvironmentError('LOB_TEST_KEY is not set')
        lob_config = lob_python.Configuration(username=api_key)

        # e. Build to/from address dicts
        addr_line1, city, state, zip_code = _parse_mailing_address(
            parcel.get('owner_mailing_address') or ''
        )
        to_address = AddressEditable(
            name=letter.get('owner_name') or parcel.get('owner_name') or 'Owner',
            address_line1=addr_line1 or '123 Unknown St',
            address_city=city or 'Philadelphia',
            address_state=state or 'PA',
            address_zip=zip_code or '19103',
        )
        from_address = AddressEditable(
            name=agent.get('agent_name', 'Steven Christie'),
            company=agent.get('brokerage', 'Keller Williams Real Estate'),
            address_line1='1286 West Chester Pike',
            address_city='West Chester',
            address_state='PA',
            address_zip='19382',
        )

        # e. Create Lob letter in test mode
        html_file = _body_to_html(letter['letter_body'])

        with lob_python.ApiClient(lob_config) as api_client:
            api = letters_api.LettersApi(api_client)
            lob_letter = api.create(LetterEditable(
                to=to_address,
                _from=from_address,
                file=html_file,
                color=False,
                double_sided=False,
                use_type=LtrUseType('marketing'),
            ))

        lob_id = lob_letter['id']
        send_date = date.today().isoformat()

        # f. Update letter row
        supabase.table('letters').update({
            'status': 'sent',
            'lob_letter_id': lob_id,
            'send_date': send_date,
        }).eq('id', letter_id).execute()

        # Update parcel status
        supabase.table('parcels').update({
            'status': 'letter_sent',
            'letter_sent_at': datetime.now(timezone.utc).isoformat(),
        }).eq('id', parcel_id).execute()

        # Insert touchpoint
        existing = (
            supabase.table('touchpoints')
            .select('id', count='exact')
            .eq('parcel_id', parcel_id)
            .execute()
        )
        touch_number = (existing.count or 0) + 1

        supabase.table('touchpoints').insert({
            'parcel_id': parcel_id,
            'channel': 'mail',
            'content': letter['letter_body'][:200],
            'sent_at': datetime.now(timezone.utc).isoformat(),
            'touch_number': touch_number,
            'version': letter.get('version', 'A'),
        }).execute()

        logger.info(f'Letter sent for parcel {parcel_id}, lob_id={lob_id}')
        return {'success': True, 'lob_letter_id': lob_id, 'send_date': send_date}

    except Exception as e:
        logger.error(f'send_letter failed: {e}', exc_info=True)
        return {'success': False, 'error': str(e)}
