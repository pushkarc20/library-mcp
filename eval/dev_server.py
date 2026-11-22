"""Demo mode: the real server running on the built-in sample library.
No Supabase account or .env file needed. Anything saved with add_link lives in memory only.

    uv run mcp dev eval/dev_server.py
"""
import fake_store

fake_store.use_fake_library()
mcp = fake_store.server.mcp