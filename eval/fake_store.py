"""Fixture-backed stand-in for the database layer. Used only by the eval.

Fake credentials are set before importing the server, so the eval can never
reach the real Supabase project. Only the four store functions are replaced;
validation, sanitizing and the approval prompt are the real server code.
"""
import json
import os
import sys
from pathlib import Path

os.environ["SUPABASE_URL"] = "https://test.invalid"
os.environ["SUPABASE_SECRET_KEY"] = "sb_secret_test_not_real"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server  # noqa: E402
import store  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures.json"


class FakeLibrary:
    def __init__(self):
        data = json.loads(FIXTURES.read_text())
        self.rows = data["links"]
        self.inserted = []  # URLs saved through add_link during this run

    def fetch_recent(self):
        return sorted(self.rows, key=lambda r: r["created_at"], reverse=True)

    def fetch_one(self, link_id):
        if not store.is_valid_id(link_id):
            return None
        for row in self.rows:
            if str(row["id"]) == link_id:
                return row
        return None

    def find_existing(self, normalized_url):
        saved = [{"id": "new", "url": u} for u in self.inserted]
        return store.find_duplicate(self.rows + saved, normalized_url)

    def insert_link(self, normalized_url):
        self.inserted.append(normalized_url)
        return len(self.rows) + len(self.inserted)


def use_fake_library():
    """Point the real server at a fresh fake library and return it."""
    library = FakeLibrary()
    store.fetch_recent = library.fetch_recent
    store.fetch_one = library.fetch_one
    store.find_existing = library.find_existing
    store.insert_link = library.insert_link
    return library