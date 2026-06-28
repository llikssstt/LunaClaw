from pathlib import Path

from agent_graph.nodes.common import flow_step
from agent_graph.uploads import get_upload_record


def multimodal_node(state):
    images = [item for item in state.get("attachments", []) if item.get("type") == "image"]
    summaries = []
    for image in images:
        upload_record = get_upload_record(image.get("file_id")) or {}
        path = Path(upload_record.get("path", ""))
        summaries.append(
            {
                "file_id": image.get("file_id"),
                "filename": upload_record.get("filename") or image.get("filename"),
                "size": path.stat().st_size if path.exists() else image.get("size"),
                "content_type": upload_record.get("content_type") or image.get("content_type", "image/*"),
                "visual_summary": f"Mock visual summary for {upload_record.get('filename') or image.get('filename') or image.get('file_id')}.",
                "ocr_text": "",
                "detected_task": "screenshot_analysis",
            }
        )
    state["vision_result"] = {"type": "image_analysis", "images": summaries}
    state.setdefault("agent_flow", []).append(flow_step("Multimodal Agent", "analyze_images", reason=f"{len(images)} image(s) processed"))
    state["route"] = "response"
    return state
