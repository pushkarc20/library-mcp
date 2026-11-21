from search import links_in_theme, search_links, theme_counts


def hidden(text):
    return "".join(chr(0xE0000 + ord(c)) for c in text)


def row(i, title, theme="Tech", bullets=("a", "b", "c"), **extra):
    base = {
        "id": i,
        "url": f"https://example.com/{i}",
        "created_at": f"2026-11-{30 - i:02d}T10:00:00Z",
        "summary": {"title": title, "theme": theme, "bullets": list(bullets), "quote": ""},
    }
    base.update(extra)
    return base


def ids(results):
    return [r["id"] for r in results]


# Rows are newest-first, like the store returns them.
ROWS = [
    row(1, "Game theory basics", "Mathematics", ["Nash equilibrium explained", "b", "c"]),
    row(2, "Ambient AI scribes in hospitals", "Healthcare", ["Clinician burnout", "Notes quality", "c"]),
    row(3, "Sourdough starter guide", "Food", ["Feeding schedule", "Hydration", "c"]),
    row(4, "Healthcare AI pilots", "Healthcare", ["Scaling pilots", "Governance", "c"]),
]


def test_every_term_must_match_and_better_matches_rank_first():
    assert ids(search_links(ROWS, "healthcare ai")) == [4, 2]
    assert ids(search_links(ROWS, "sourdough hospitals")) == []


def test_matches_word_prefixes_but_not_mid_word():
    assert ids(search_links(ROWS, "health")) == [4, 2]
    assert ids(search_links(ROWS, "ai")) == [2, 4]   # "explained" in row 1 must not match


def test_title_match_outranks_newer_body_match():
    rows = [
        row(11, "Other", bullets=["notes about bread", "b", "c"]),   # newer, body match only
        row(10, "Notes on cooking"),                                 # older, title match
    ]
    assert ids(search_links(rows, "notes")) == [10, 11]


def test_ties_keep_newest_first():
    rows = [row(20, "A guide"), row(21, "Another guide")]
    assert ids(search_links(rows, "guide")) == [20, 21]


def test_limit_and_theme_filter():
    assert ids(search_links(ROWS, "ai", limit=1)) == [2]
    assert ids(search_links(ROWS, "ai", theme="HEALTHCARE")) == [2, 4]
    assert ids(search_links(ROWS, "ai", theme="food")) == []


def test_results_expose_only_listing_fields():
    result = search_links(ROWS, "sourdough")[0]
    assert set(result) == {"id", "url", "title", "theme", "saved_at"}


def test_empty_and_hostile_queries_are_safe():
    for q in ("", "   ", hidden("x"), "(.*", "x " * 500, "[a-", "\\"):
        assert search_links(ROWS, q) == []


def test_never_searches_content_raw_message_or_error():
    rows = [row(30, "Unrelated", content="needle", raw_message="needle", error="needle")]
    assert search_links(rows, "needle") == []


def test_rows_without_a_usable_summary_are_skipped():
    rows = ROWS + [row(31, "T", summary=None), row(32, "T", summary={"theme": "x"})]
    found = ids(search_links(rows, "t"))
    assert 31 not in found and 32 not in found
    assert [c["count"] for c in theme_counts(rows)] == [2, 1, 1]


def test_theme_counts_group_case_insensitively():
    rows = ROWS + [row(5, "x", "healthcare")]
    assert theme_counts(rows) == [
        {"theme": "Healthcare", "count": 3},
        {"theme": "Food", "count": 1},
        {"theme": "Mathematics", "count": 1},
    ]


def test_links_in_theme():
    assert ids(links_in_theme(ROWS, "healthcare")) == [2, 4]
    assert ids(links_in_theme(ROWS, "Healthcare", limit=1)) == [2]
    assert links_in_theme(ROWS, "nonexistent") == []