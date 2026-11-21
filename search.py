"""Pure search and grouping over rows the store already fetched. No network, no MCP.

Rows are expected newest-first, so ties in ranking keep recent links on top.
"""
import re

from sanitize import MAX_THEME, clean_text, link_detail, link_listing

MAX_QUERY = 100
MAX_TERMS = 8


def _terms(query):
    cleaned = clean_text(query, MAX_QUERY).lower()
    return [t for t in cleaned.split(" ") if t][:MAX_TERMS]


def _prefix_pattern(term):
    """Match the term at the start of a word, so 'ai' does not match inside 'explained'."""
    return re.compile(r"(?<!\w)" + re.escape(term))


def _score(detail, patterns):
    title = detail["title"].lower()
    body = " ".join([*detail["bullets"], detail["quote"], detail["theme"]]).lower()
    url = detail["url"].lower()
    score = 0
    for p in patterns:
        in_title, in_body, in_url = bool(p.search(title)), bool(p.search(body)), bool(p.search(url))
        if not (in_title or in_body or in_url):
            return 0  # every term must match somewhere
        score += 3 * in_title + in_body + in_url
    return score


def _theme_key(theme):
    return clean_text(theme, MAX_THEME).lower()


def search_links(rows, query, theme=None, limit=10):
    terms = _terms(query)
    if not terms:
        return []
    patterns = [_prefix_pattern(t) for t in terms]
    theme_key = _theme_key(theme) if theme is not None else None

    scored = []
    for row in rows:
        detail = link_detail(row)
        if detail is None:
            continue
        if theme_key is not None and detail["theme"].lower() != theme_key:
            continue
        score = _score(detail, patterns)
        if score:
            scored.append((score, row))

    scored.sort(key=lambda pair: pair[0], reverse=True)  # stable: ties stay newest-first
    return [link_listing(row) for _, row in scored[:limit]]


def theme_counts(rows):
    """Themes with counts, grouped case-insensitively, biggest first."""
    counts, names = {}, {}
    for row in rows:
        listing = link_listing(row)
        if listing is None:
            continue
        key = listing["theme"].lower()
        names.setdefault(key, listing["theme"])
        counts[key] = counts.get(key, 0) + 1
    result = [{"theme": names[k], "count": n} for k, n in counts.items()]
    result.sort(key=lambda item: (-item["count"], item["theme"].lower()))
    return result


def links_in_theme(rows, theme, limit=50):
    key = _theme_key(theme)
    found = []
    for row in rows:
        listing = link_listing(row)
        if listing is not None and listing["theme"].lower() == key:
            found.append(listing)
            if len(found) == limit:
                break
    return found