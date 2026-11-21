"""MCP server over the saved-links library. Read-only tools; local stdio use."""
import logging
import os
from pathlib import Path
from typing import Annotated

from dotenv import load_dotenv
from pydantic import BaseModel, Field

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

import search
import store
from sanitize import envelope, link_detail

load_dotenv(Path(__file__).parent / ".env")

# Logs go to stderr. Never print() to stdout: stdout carries the MCP protocol itself.
logging.basicConfig(level=logging.INFO)

for _name in ("SUPABASE_URL", "SUPABASE_SECRET_KEY"):
    if not os.environ.get(_name):
        raise SystemExit(f"Missing {_name}. Copy .env.example to .env and fill it in.")

mcp = MCPServer("Later Library")

READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=False)

EMPTY_SEARCH_HINT = (
    "No matches. Try fewer or different keywords, or call list_by_theme() "
    "with no arguments to browse by theme."
)


class LinkListing(BaseModel):
    id: int | str
    url: str
    title: str
    theme: str
    saved_at: str


class LinkDetail(LinkListing):
    bullets: list[str]
    quote: str


class ThemeCount(BaseModel):
    theme: str
    count: int


class SearchResponse(BaseModel):
    notice: str
    count: int
    results: list[LinkListing]
    hint: str | None = None


class SummaryResponse(BaseModel):
    notice: str
    link: LinkDetail


class ThemesResponse(BaseModel):
    notice: str
    themes: list[ThemeCount] | None = None
    links: list[LinkListing] | None = None
    hint: str | None = None


@mcp.tool(title="Search saved links", annotations=READ_ONLY)
def search_links(
    query: Annotated[str, Field(
        min_length=1, max_length=100,
        description="Keywords to find in titles, summaries and URLs. Every word must match.",
    )],
    theme: Annotated[str | None, Field(
        max_length=30,
        description="Optional: only links in this theme. Call list_by_theme() to see valid themes.",
    )] = None,
    limit: Annotated[int, Field(ge=1, le=20, description="Maximum number of results.")] = 10,
) -> SearchResponse:
    """Search the user's saved read-it-later library by keyword.

    Returns matching links with id, url, title and theme, best matches first.
    Use get_summary with an id to read the full summary.
    """
    hits = search.search_links(store.fetch_recent(), query, theme, limit)
    return SearchResponse(**envelope(
        count=len(hits), results=hits, hint=None if hits else EMPTY_SEARCH_HINT,
    ))


@mcp.tool(title="Get a link's summary", annotations=READ_ONLY)
def get_summary(
    link_id: Annotated[str, Field(
        min_length=1, max_length=64,
        description="The id of a link, as returned by search_links or list_by_theme.",
    )],
) -> SummaryResponse:
    """Get the saved summary (title, three bullets, a quote) for one link by id."""
    if not store.is_valid_id(link_id):
        raise ToolError(
            "That is not a valid link id. Ids come from search_links or list_by_theme results."
        )
    row = store.fetch_one(link_id)
    detail = link_detail(row) if row else None
    if detail is None:
        raise ToolError(
            "No summarized link has that id. Use search_links or list_by_theme to find valid ids."
        )
    return SummaryResponse(**envelope(link=detail))


@mcp.tool(title="Browse links by theme", annotations=READ_ONLY)
def list_by_theme(
    theme: Annotated[str | None, Field(
        max_length=30,
        description="Theme name, for example 'Healthcare'. Omit it to list every theme with counts.",
    )] = None,
    limit: Annotated[int, Field(ge=1, le=100, description="Maximum number of links to return.")] = 50,
) -> ThemesResponse:
    """Browse the library by theme.

    With no theme, returns every theme and how many links it holds.
    With a theme, returns that theme's links, newest first.
    """
    rows = store.fetch_recent()
    if theme is None:
        return ThemesResponse(**envelope(themes=search.theme_counts(rows)))
    links = search.links_in_theme(rows, theme, limit)
    hint = None if links else (
        "No links in that theme. Call list_by_theme() with no arguments to see valid themes."
    )
    return ThemesResponse(**envelope(links=links, hint=hint))