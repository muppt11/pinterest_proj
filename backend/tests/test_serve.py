"""Production server: API under /api, SPA fallback, and no file access outside the built frontend."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import serve


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>shell</html>")
    (dist / "logo.webp").write_bytes(b"RIFF")
    (tmp_path / "secret.txt").write_text("do not serve")
    monkeypatch.setattr(serve, "DIST", dist)
    return TestClient(serve.app)


def test_api_is_mounted_under_api(client: TestClient) -> None:
    assert client.get("/api/health").json()["app"] == "MoodBoards"


def test_client_routes_fall_back_to_the_app_shell(client: TestClient) -> None:
    for path in ("/", "/item/abc", "/trips/3", "/t/some-slug"):
        assert client.get(path).text == "<html>shell</html>"
    assert client.get("/logo.webp").content == b"RIFF"


def test_no_path_traversal(client: TestClient) -> None:
    for path in ("/../secret.txt", "/%2e%2e/secret.txt", "/..%2fsecret.txt"):
        assert "do not serve" not in client.get(path).text
