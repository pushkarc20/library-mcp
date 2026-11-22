"""Checks that the fake library works through the real server. No AI model involved."""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fake_store  # noqa: E402

from mcp.client import Client  # noqa: E402
from mcp.types import ElicitResult  # noqa: E402


async def approve(context, params):
    return ElicitResult(action="accept", content={"ok": True})


results = []


def check(label, condition):
    results.append(bool(condition))
    print(("PASS  " if condition else "FAIL  ") + label)


async def call(client, tool, args):
    result = await client.call_tool(tool, args)
    return json.loads(result.content[0].text)


async def main():
    library = fake_store.use_fake_library()
    async with Client(fake_store.server.mcp, elicitation_callback=approve) as client:
        data = await call(client, "list_by_theme", {})
        themes = {t["theme"]: t["count"] for t in data["themes"]}
        check("themes and counts", themes == {"Economics": 2, "Healthcare": 3, "AI": 2, "Productivity": 3})

        data = await call(client, "search_links", {"query": "nash"})
        check("search finds only the Nash article", [r["id"] for r in data["results"]] == [2])

        data = await call(client, "get_summary", {"link_id": "10"})
        check("poisoned entry is returned as data, with the notice",
              "IGNORE PREVIOUS" in " ".join(data["link"]["bullets"]) and "notice" in data)

        data = await call(client, "add_link", {"url": "https://example.org/great-article"})
        check("approved add_link saves", data["status"] == "saved"
              and library.inserted == ["https://example.org/great-article"])

        data = await call(client, "add_link", {"url": "https://example.org/great-article"})
        check("same link again is a duplicate", data["status"] == "already_saved"
              and len(library.inserted) == 1)

    sys.exit(0 if all(results) else 1)


asyncio.run(main())