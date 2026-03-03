import os
from supabase import create_client, Client


def get_client() -> Client:
    url = os.environ.get('SUPABASE_URL')
    key = os.environ.get('SUPABASE_KEY')

    if not url:
        raise EnvironmentError(
            "SUPABASE_URL is not set. Add it to your .env file."
        )
    if not key:
        raise EnvironmentError(
            "SUPABASE_KEY is not set. Add it to your .env file."
        )

    return create_client(url, key)
