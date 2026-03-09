"""
LandFinder — Sprint 5 test suite.

Tests Lob (mail), SendGrid (email), and Twilio (SMS) sending layers,
plus the outreach coordinator.

IMPORTANT: Set VERIFIED_PHONE below to your Twilio-verified number
before running. Twilio trial accounts can only text verified numbers.
"""

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(levelname)s — %(message)s')

from functions.db import get_client
from functions.outreach_generator import generate_outreach
from functions.mail_sender import send_letter
from functions.email_sender import send_email
from functions.sms_sender import send_sms
from functions.outreach_coordinator import coordinate_outreach

# ── Replace with your Twilio-verified number ─────────────────────────────────
VERIFIED_PHONE = '+14846537644'
# ─────────────────────────────────────────────────────────────────────────────

DIVIDER = '─' * 70


def print_section(title):
    print(f'\n{"═" * 70}')
    print(f'  {title}')
    print(f'{"═" * 70}\n')


def run_tests():
    print_section('LandFinder Sprint 5 Tests')

    assert VERIFIED_PHONE != '+1XXXXXXXXXX', (
        'Set VERIFIED_PHONE at the top of test_sprint5.py to your '
        'Twilio-verified number before running.'
    )

    supabase = get_client()

    # ── Setup: seed parcel ───────────────────────────────────────────────────
    result = supabase.table('parcels').select('*').eq('mls_id', 'MLS123456').execute()
    assert result.data, 'Seed parcel MLS123456 not found'
    parcel_id = result.data[0]['id']
    print(f'Seed parcel ID: {parcel_id}')

    # b. Set test contact data
    supabase.table('parcels').update({
        'owner_name': 'George & Martha Williams',
        'owner_mailing_address': '456 Owner Lane, Philadelphia PA 19103',
        'township': 'Birmingham',
        'lot_size_acres': 5.2,
        'owner_email': 'brianmchristie8@gmail.com',
        'owner_phone': VERIFIED_PHONE,
        'status': 'approved',
        'source_type': 'mls_active',
    }).eq('id', parcel_id).execute()
    print('Seed parcel updated with test contact data\n')

    # Ensure a draft mail letter exists
    draft_check = (
        supabase.table('letters')
        .select('id')
        .eq('parcel_id', parcel_id)
        .eq('status', 'draft')
        .limit(1)
        .execute()
    )
    if not draft_check.data:
        print('No draft letter found — generating one now...')
        gen = generate_outreach(parcel_id, 'steven_christie', 'mail', touch_number=1)
        assert gen, 'generate_outreach failed during setup'
        print('Draft letter created\n')
    else:
        print(f'Draft letter already exists (id={draft_check.data[0]["id"]})\n')

    # ── TEST 1: Send mail via Lob ────────────────────────────────────────────
    print_section('TEST 1 — Send mail via Lob (test mode)')

    mail_result = send_letter(parcel_id, 'steven_christie')
    print(f'Result: {mail_result}')
    assert mail_result.get('success'), f'send_letter failed: {mail_result}'
    assert mail_result.get('lob_letter_id'), 'Missing lob_letter_id'

    # Confirm letter status updated in Supabase
    letter_check = (
        supabase.table('letters')
        .select('status, lob_letter_id')
        .eq('parcel_id', parcel_id)
        .eq('status', 'sent')
        .limit(1)
        .execute()
    )
    assert letter_check.data, 'Letter status not updated to sent in Supabase'
    print(f'Letter status in Supabase: {letter_check.data[0]["status"]} ✓')
    print(f'lob_letter_id: {letter_check.data[0]["lob_letter_id"]} ✓')

    # Confirm touchpoint inserted
    tp_mail = (
        supabase.table('touchpoints')
        .select('id, channel')
        .eq('parcel_id', parcel_id)
        .eq('channel', 'mail')
        .execute()
    )
    assert tp_mail.data, 'Mail touchpoint not found in Supabase'
    print(f'Mail touchpoint inserted ✓\n')

    # ── TEST 2: Send email via SendGrid ─────────────────────────────────────
    print_section('TEST 2 — Send email via SendGrid')

    email_result = send_email(parcel_id, 'steven_christie')
    print(f'Result: {email_result}')
    assert email_result.get('success'), f'send_email failed: {email_result}'
    assert email_result.get('message_id') is not None, 'Missing message_id'

    # Confirm touchpoint
    tp_email = (
        supabase.table('touchpoints')
        .select('id, channel')
        .eq('parcel_id', parcel_id)
        .eq('channel', 'email')
        .execute()
    )
    assert tp_email.data, 'Email touchpoint not found in Supabase'
    print(f'Email touchpoint inserted ✓\n')

    # ── TEST 3: Send SMS via Twilio ──────────────────────────────────────────
    print_section('TEST 3 — Send SMS via Twilio')

    sms_result = send_sms(parcel_id, 'steven_christie')
    print(f'Result: {sms_result}')
    assert sms_result.get('success'), f'send_sms failed: {sms_result}'
    assert sms_result.get('message_sid'), 'Missing message_sid'

    # Confirm touchpoint
    tp_sms = (
        supabase.table('touchpoints')
        .select('id, channel')
        .eq('parcel_id', parcel_id)
        .eq('channel', 'sms')
        .execute()
    )
    assert tp_sms.data, 'SMS touchpoint not found in Supabase'
    print(f'SMS touchpoint inserted ✓\n')

    # ── TEST 4: Full coordinator ─────────────────────────────────────────────
    print_section('TEST 4 — Full coordinator (all 3 channels)')

    # Reset parcel and clear touchpoints from tests 1–3
    supabase.table('parcels').update({'status': 'approved'}).eq('id', parcel_id).execute()
    supabase.table('touchpoints').delete().eq('parcel_id', parcel_id).execute()

    # Generate a fresh draft letter for mail_sender to pick up
    fresh = generate_outreach(parcel_id, 'steven_christie', 'mail', touch_number=1)
    assert fresh, 'generate_outreach failed during coordinator setup'
    print('Fresh draft letter generated for coordinator test\n')

    summary = coordinate_outreach(parcel_id, 'steven_christie')
    print('Coordinator summary:')
    for k, v in summary.items():
        print(f'  {k}: {v}')

    assert summary.get('sent'), f'coordinator did not send: {summary}'
    assert summary.get('channels_sent') == 3, (
        f'Expected channels_sent=3, got {summary.get("channels_sent")}'
    )

    # Confirm all 3 touchpoints in Supabase
    all_tps = (
        supabase.table('touchpoints')
        .select('channel')
        .eq('parcel_id', parcel_id)
        .execute()
    )
    channels = {tp['channel'] for tp in all_tps.data}
    assert 'mail' in channels, 'Missing mail touchpoint after coordinator'
    assert 'email' in channels, 'Missing email touchpoint after coordinator'
    assert 'sms' in channels, 'Missing sms touchpoint after coordinator'
    print(f'\nAll 3 touchpoints confirmed in Supabase: {sorted(channels)} ✓')
    print(f'channels_sent: {summary["channels_sent"]} ✓\n')

    # ── TEST 5: No phone number handling ────────────────────────────────────
    print_section('TEST 5 — Graceful handling of missing phone number')

    supabase.table('parcels').update({'owner_phone': None}).eq('id', parcel_id).execute()

    no_phone_result = send_sms(parcel_id, 'steven_christie')
    print(f'Result: {no_phone_result}')
    assert no_phone_result.get('success') is False, 'Expected success=False'
    assert no_phone_result.get('reason') == 'no_phone', (
        f'Expected reason=no_phone, got {no_phone_result.get("reason")}'
    )
    print('Graceful no_phone handling confirmed ✓')

    # Restore phone
    supabase.table('parcels').update(
        {'owner_phone': VERIFIED_PHONE}
    ).eq('id', parcel_id).execute()
    print('owner_phone restored\n')

    print('═' * 70)
    print('  Sprint 5 complete')
    print('═' * 70)


if __name__ == '__main__':
    run_tests()
