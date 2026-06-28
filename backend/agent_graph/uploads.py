import json
from pathlib import Path


DEFAULT_UPLOADS_INDEX_PATH = Path(__file__).resolve().parents[1] / "storage" / "uploads_index.json"


def register_upload(record, index_path=None):
    path = Path(index_path or DEFAULT_UPLOADS_INDEX_PATH)
    data = _read_index(path)
    data[record["file_id"]] = record
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return record


def get_upload_record(file_id, index_path=None):
    return _read_index(Path(index_path or DEFAULT_UPLOADS_INDEX_PATH)).get(file_id)


def _read_index(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
