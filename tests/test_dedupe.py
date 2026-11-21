from store import find_duplicate

ROWS = [
    {"id": 1, "url": "http://old.example.com/"},           # legacy http: can't match, must be skipped
    {"id": 2, "url": "https://Example.com/a?utm_source=x#top"},
    {"id": 3, "url": None},                                  # broken row must not crash the scan
    {"id": 4, "url": "https://en.wikipedia.org/wiki/Foo_(bar)"},
]


def test_matches_after_normalizing_stored_url():
    assert find_duplicate(ROWS, "https://example.com/a") == 2


def test_matches_exact_url():
    assert find_duplicate(ROWS, "https://en.wikipedia.org/wiki/Foo_(bar)") == 4


def test_no_match_returns_none():
    assert find_duplicate(ROWS, "https://example.com/b") is None


def test_empty_library():
    assert find_duplicate([], "https://example.com/a") is None