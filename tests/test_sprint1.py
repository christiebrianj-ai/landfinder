"""
LandFinder — Sprint 1 test suite.

Verifies:
  - Supabase connection is working
  - All 5 tables exist and are queryable
  - Seed parcel (MLS123456) is present
  - Agent config for steven_christie is present
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from functions.db import get_client


def run_tests():
    print("=== LandFinder Sprint 1 Tests ===\n")

    supabase = get_client()
    print("Supabase client initialized\n")

    # --- Row counts for all 5 tables ---
    tables = ['parcels', 'letters', 'touchpoints', 'agent_decisions', 'agent_configs']
    print("Table row counts:")
    for table in tables:
        result = supabase.table(table).select('*', count='exact').execute()
        count = result.count if result.count is not None else len(result.data)
        print(f"  {table}: {count} row(s)")

    # --- Seed parcel ---
    print("\n--- Seed Parcel (MLS123456) ---")
    result = supabase.table('parcels').select('*').eq('mls_id', 'MLS123456').execute()
    if result.data:
        for key, value in result.data[0].items():
            print(f"  {key}: {value}")
    else:
        print("  ERROR: seed parcel not found")

    # --- Agent config ---
    print("\n--- Agent Config (steven_christie) ---")
    result = supabase.table('agent_configs').select('*').eq('agent_id', 'steven_christie').execute()
    if result.data:
        for key, value in result.data[0].items():
            print(f"  {key}: {value}")
    else:
        print("  ERROR: agent config not found")

    print("\n=== Tests complete ===")


if __name__ == '__main__':
    run_tests()
