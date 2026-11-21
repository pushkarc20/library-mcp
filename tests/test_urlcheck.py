import pytest

from sanitize import MAX_URL
from urlcheck import UrlRejected, normalize_url


@pytest.mark.parametrize("raw, expected", [
    ("https://Example.com/Path?a=1#frag", "https://example.com/Path?a=1"),
    ("https://example.com", "https://example.com/"),
    ("  https://example.com/x  ", "https://example.com/x"),
    ("https://example.com:443/x", "https://example.com/x"),
    ("https://example.com./x", "https://example.com/x"),
    ("https://example.com/x?utm_source=a&id=5&fbclid=z", "https://example.com/x?id=5"),
    ("https://example.com/x?utm_source=a", "https://example.com/x"),
    ("https://en.wikipedia.org/wiki/Foo_(bar)", "https://en.wikipedia.org/wiki/Foo_(bar)"),
])
def test_accepts_and_normalizes(raw, expected):
    assert normalize_url(raw) == expected
    assert normalize_url(expected) == expected  # normalizing twice changes nothing


@pytest.mark.parametrize("raw", [
    "",
    "   ",
    "http://example.com/",
    "ftp://example.com/file",
    "javascript:alert(1)",
    "file:///etc/passwd",
    "https://user:pw@example.com/",
    "https://example.com@evil.com/",
    "https://localhost/",
    "https://127.0.0.1/",
    "https://10.0.0.5/x",
    "https://169.254.169.254/latest/meta-data",
    "https://[::1]/",
    "https://2130706433/",
    "https://0x7f.0.0.1/",
    "https://intranet/",
    "https://printer.local/",
    "https://service.internal/",
    "https://example.com:8443/",
    "https://exa mple.com/",
    "https://exa_mple.com/",
    "https://.example.com/",
    "https://example.com/\u200bx",
    "https://example.com/a\nb",
    "https://" + "a" * (MAX_URL + 10) + ".com/",
])
def test_rejects(raw):
    with pytest.raises(UrlRejected):
        normalize_url(raw)


def test_non_text_rejected():
    with pytest.raises(UrlRejected):
        normalize_url(None)