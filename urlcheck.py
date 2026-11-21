"""Validation and normalization for URLs submitted through add_link.

Rules: https only, no credentials, no IP addresses, no internal hostnames,
no odd ports, no control or invisible characters. Tracking parameters and
fragments are stripped so the same page is stored the same way every time.
"""
import ipaddress
import re
import unicodedata
from urllib.parse import urlsplit, urlunsplit

from sanitize import MAX_URL

TRACKING_KEYS = {
    "fbclid", "gclid", "dclid", "msclkid", "mc_cid", "mc_eid",
    "igshid", "_hsenc", "_hsmi",
}
BLOCKED_SUFFIXES = (
    ".local", ".localhost", ".internal", ".lan", ".home.arpa", ".corp", ".intranet",
)
HOST_CHARS = re.compile(r"[a-z0-9.-]+")
TLD_PATTERN = re.compile(r"[a-z][a-z0-9-]*")  # must start with a letter: rules out 127.1, 0x7f etc.


class UrlRejected(ValueError):
    """The message is safe to show to the model and the user."""


def _strip_tracking(query):
    kept = []
    for part in query.split("&"):
        if not part:
            continue
        key = part.split("=", 1)[0].lower()
        if key.startswith("utm_") or key in TRACKING_KEYS:
            continue
        kept.append(part)
    return "&".join(kept)


def normalize_url(raw):
    """Return the cleaned URL, or raise UrlRejected with a reason."""
    if not isinstance(raw, str):
        raise UrlRejected("The URL must be text.")
    url = raw.strip()
    if not url:
        raise UrlRejected("The URL is empty.")
    if len(url) > MAX_URL:
        raise UrlRejected(f"The URL is longer than {MAX_URL} characters.")
    if any(unicodedata.category(ch).startswith("C") for ch in url) or any(ch.isspace() for ch in url):
        raise UrlRejected("The URL contains spaces or control characters.")

    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        raise UrlRejected("The URL is not well formed.")

    if parts.scheme.lower() != "https":
        raise UrlRejected("Only https:// links can be saved.")
    if "@" in parts.netloc:
        raise UrlRejected("Links containing a username or password are not allowed.")
    if port not in (None, 443):
        raise UrlRejected("Links with a custom port are not allowed.")

    host = (parts.hostname or "").lower().rstrip(".")
    if not host:
        raise UrlRejected("The URL has no hostname.")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise UrlRejected("Links to IP addresses are not allowed.")
    if not HOST_CHARS.fullmatch(host):
        raise UrlRejected("The hostname contains characters that are not allowed.")
    labels = host.split(".")
    if len(labels) < 2 or any(not label for label in labels):
        raise UrlRejected("The hostname must be a public domain such as example.com.")
    if host.endswith(BLOCKED_SUFFIXES):
        raise UrlRejected("Internal or local hostnames are not allowed.")
    if not TLD_PATTERN.fullmatch(labels[-1]):
        raise UrlRejected("The hostname must end in a real domain suffix such as .com.")

    path = parts.path or "/"
    query = _strip_tracking(parts.query)
    return urlunsplit(("https", host, path, query, ""))