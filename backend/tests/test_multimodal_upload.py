from pathlib import Path

from fastapi.testclient import TestClient

from main import app


def test_upload_image_saves_file_and_returns_attachment_shape():
    client = TestClient(app)
    response = client.post("/uploads/image", files={"file": ("shot.png", b"fake image", "image/png")})

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["type"] == "image"
    assert payload["file_id"].startswith("img_")
    path = Path(payload["path"])
    assert path.exists()
    path.unlink()

