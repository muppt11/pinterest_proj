"""Server-side Google Lens upload (network mocked)."""

from pathlib import Path

import pytest

from app.services.lens import lens_results_url


def test_returns_google_results_url_from_redirect(tmp_path: Path) -> None:
    img = tmp_path / "a.jpg"
    img.write_bytes(b"\xff\xd8jpeg")
    seen = {}

    def post(req):  # type: ignore[no-untyped-def]
        seen["url"], seen["body"], seen["headers"] = req.full_url, req.data, dict(req.headers)
        return 303, "https://www.google.com/search?vsrid=abc&udm=26"

    assert lens_results_url(img, post) == "https://www.google.com/search?vsrid=abc&udm=26"
    assert seen["url"].startswith("https://lens.google.com/v3/upload?")
    assert b'name="encoded_image"' in seen["body"] and b"\xff\xd8jpeg" in seen["body"]
    assert "Origin" not in seen["headers"]  # the reason this runs server-side


@pytest.mark.parametrize("status,location", [(400, None), (303, "https://evil.example/phish"), (200, None)])
def test_rejects_errors_and_unexpected_redirects(tmp_path: Path, status: int, location: str | None) -> None:
    img = tmp_path / "a.jpg"
    img.write_bytes(b"x")
    with pytest.raises(RuntimeError):
        lens_results_url(img, lambda req: (status, location))
