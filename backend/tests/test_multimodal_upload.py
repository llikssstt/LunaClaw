from pathlib import Path

from fastapi.testclient import TestClient

from agent_graph import uploads
from main import app


def test_upload_image_saves_file_without_returning_server_path(monkeypatch):
    tmp_dir = Path(__file__).resolve().parents[2] / ".pytest_tmp" / "upload_contract"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(uploads, "DEFAULT_UPLOADS_INDEX_PATH", tmp_dir / "uploads_index.json")
    client = TestClient(app)

    response = client.post("/uploads/image", files={"file": ("shot.png", b"fake image", "image/png")})

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["type"] == "image"
    assert payload["file_id"].startswith("img_")
    assert "path" not in payload
    record = uploads.get_upload_record(payload["file_id"])
    assert record is not None
    assert Path(record["path"]).exists()
    Path(record["path"]).unlink()
