"""Approval-flow tests for add_link. No real database or network is used."""
import json
import os

# Fake credentials, set BEFORE importing server, so these tests can never touch the real database.
os.environ["SUPABASE_URL"] = "https://test.invalid"
os.environ["SUPABASE_SECRET_KEY"] = "sb_secret_test_not_real"

import pytest  # noqa: E402
from mcp.client import Client  # noqa: E402
from mcp.types import ElicitResult  # noqa: E402

import server  # noqa: E402

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def db(monkeypatch):
    state = {"existing": None, "inserted": []}
    monkeypatch.setattr(server.store, "find_existing", lambda url: state["existing"])

    def fake_insert(url):
        state["inserted"].append(url)
        return 123

    monkeypatch.setattr(server.store, "insert_link", fake_insert)
    return state


def make_callback(action, content=None):
    """A fake 'human' that answers the approval prompt and remembers what it was shown."""
    seen = []

    async def callback(context, params):
        seen.append(params.message)
        return ElicitResult(action=action, content=content)

    callback.seen = seen
    return callback


async def call_add_link(url, callback=None):
    kwargs = {"elicitation_callback": callback} if callback else {}
    async with Client(server.mcp, **kwargs) as client:
        return await client.call_tool("add_link", {"url": url})


def body(result):
    return result.content[0].text


async def test_approved_link_is_saved_in_clean_form(db):
    human = make_callback("accept", {"ok": True})
    result = await call_add_link("https://Example.com/a?utm_source=x#frag", human)
    assert json.loads(body(result))["status"] == "saved"
    assert db["inserted"] == ["https://example.com/a"]


async def test_prompt_shows_the_exact_clean_url(db):
    human = make_callback("accept", {"ok": True})
    await call_add_link("https://Example.com/a?utm_source=x#frag", human)
    assert len(human.seen) == 1
    assert "https://example.com/a" in human.seen[0]
    assert "utm_source" not in human.seen[0]


async def test_decline_saves_nothing(db):
    result = await call_add_link("https://example.com/a", make_callback("decline"))
    assert json.loads(body(result))["status"] == "not_saved"
    assert db["inserted"] == []


async def test_cancel_saves_nothing(db):
    result = await call_add_link("https://example.com/a", make_callback("cancel"))
    assert json.loads(body(result))["status"] == "not_saved"
    assert db["inserted"] == []


async def test_accept_without_ticking_the_box_saves_nothing(db):
    result = await call_add_link("https://example.com/a", make_callback("accept", {"ok": False}))
    assert json.loads(body(result))["status"] == "not_saved"
    assert db["inserted"] == []


async def test_client_that_cannot_ask_saves_nothing(db):
    try:
        result = await call_add_link("https://example.com/a")  # no callback registered
    except Exception:
        result = None  # the SDK may raise instead of returning an error result
    if result is not None:
        assert '"saved"' not in body(result)
    assert db["inserted"] == []


async def test_invalid_url_is_rejected_and_human_is_never_asked(db):
    human = make_callback("accept", {"ok": True})
    result = await call_add_link("http://localhost/admin", human)
    assert "Link not saved" in body(result)
    assert human.seen == []
    assert db["inserted"] == []


async def test_duplicate_is_reported_and_human_is_never_asked(db):
    db["existing"] = 7
    human = make_callback("accept", {"ok": True})
    result = await call_add_link("https://example.com/a", human)
    assert json.loads(body(result))["status"] == "already_saved"
    assert human.seen == []
    assert db["inserted"] == []