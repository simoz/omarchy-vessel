"""Small HTTPS JSON requests for location services; AIS uses its own transport."""

import json
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

USER_AGENT = "omarchy-vessel (https://github.com/simoz/omarchy-vessel)"


def require_https(url):
    parts = urlsplit(url)
    if (
        parts.scheme != "https"
        or not parts.hostname
        or parts.username is not None
        or parts.password is not None
    ):
        raise ValueError("Expected an HTTPS URL without credentials")


class HTTPSRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        # urllib normally permits HTTPS -> HTTP redirects. A location query
        # must not silently become plaintext because a provider redirects it.
        require_https(new_url)
        return super().redirect_request(
            request, response, code, message, headers, new_url
        )


def fetch_json(url, *, max_bytes):
    """Bound response size and time, and keep server content out of error messages."""
    require_https(url)
    request = Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
    )
    opener = build_opener(HTTPSRedirectHandler())
    with opener.open(request, timeout=12) as response:
        raw = response.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise ValueError("Location response is too large")
    try:
        return json.loads(raw)
    except RecursionError as error:
        raise ValueError("Invalid location response") from error
