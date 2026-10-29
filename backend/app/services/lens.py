"""Google Lens search-by-image link for a catalog photo, created server-side.

The browser can't do this reliably: Google rejects uploads that carry a site's Origin header
(measured: Origin of any site -> 403/400; no Origin -> 303 to the results page). A server request
has no Origin, so the backend uploads the catalog image and returns Google's results URL.
The upload endpoint isn't officially documented, so the UI keeps fallbacks.
"""

import time
import urllib.request
import uuid
from collections.abc import Callable
from pathlib import Path

LENS_UPLOAD = "https://lens.google.com/v3/upload"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return None  # we want the Location header, not the page


def _post(request: urllib.request.Request) -> tuple[int, str | None]:
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(request, timeout=20) as r:
            return r.status, r.headers.get("Location")
    except urllib.error.HTTPError as e:  # 3xx arrive here when redirects aren't followed
        return e.code, e.headers.get("Location")


def lens_results_url(image_path: Path, post: Callable[[urllib.request.Request], tuple[int, str | None]] = _post) -> str:
    """Upload the image to Google Lens and return the results URL. Raises RuntimeError on failure."""
    boundary = uuid.uuid4().hex
    body = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"encoded_image\"; filename=\"item.jpg\"\r\n"
        f"Content-Type: image/jpeg\r\n\r\n"
    ).encode() + image_path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    request = urllib.request.Request(
        f"{LENS_UPLOAD}?ep=gsbubb&st={int(time.time() * 1000)}",
        data=body,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}", "User-Agent": USER_AGENT},
    )
    status, location = post(request)
    if status in (301, 302, 303, 307, 308) and location and location.startswith("https://www.google.com/"):
        return location
    raise RuntimeError(f"Google Lens didn't return a results page (status {status}).")
