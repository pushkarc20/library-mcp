"""Read-only access to the saved-links table in Supabase.

Only allowlisted columns are ever selected, so page content, raw chat messages
and error text never leave the database.
"""
import os
import re

from supabase import create_client

TABLE = "links"
COLUMNS = "id,url,created_at,summary"  # allowlist: no content, raw_message or error
READABLE_STATUSES = ["summarized", "sent"]
FETCH_LIMIT = 500
ID_PATTERN = re.compile(r"^(\d{1,18}|[0-9a-fA-F-]{36})$")  # integer or UUID ids only

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])
    return _client


def is_valid_id(link_id):
    return isinstance(link_id, str) and bool(ID_PATTERN.match(link_id))


def fetch_recent():
    """Newest-first rows that have a summary. Capped, so the library is read in bulk once."""
    result = (
        _get_client()
        .table(TABLE)
        .select(COLUMNS)
        .in_("status", READABLE_STATUSES)
        .order("created_at", desc=True)
        .limit(FETCH_LIMIT)
        .execute()
    )
    return result.data or []


def fetch_one(link_id):
    if not is_valid_id(link_id):
        return None
    result = (
        _get_client()
        .table(TABLE)
        .select(COLUMNS)
        .in_("status", READABLE_STATUSES)
        .eq("id", link_id)
        .limit(1)
        .execute()
    )
    rows = result.data or []
    return rows[0] if rows else None