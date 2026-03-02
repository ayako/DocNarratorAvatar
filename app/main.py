"""DocNarratorAvatar – FastAPI backend entry point.

Endpoints
---------
POST /api/process           Upload a document and start the processing pipeline.
GET  /api/status/{job_id}   Poll processing status and progress.
GET  /api/result/{job_id}   Retrieve completed results (video URL + captions).
GET  /api/video/{job_id}    Stream the generated MP4 video.
GET  /                      Serve the single-page frontend.
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from typing import Any, Dict

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_HERE = os.path.dirname(os.path.abspath(__file__))
_STATIC_DIR = os.path.join(_HERE, "static")
_UPLOAD_DIR = os.path.join(_HERE, "..", "uploads")
_OUTPUT_DIR = os.path.join(_HERE, "..", "outputs")

os.makedirs(_UPLOAD_DIR, exist_ok=True)
os.makedirs(_OUTPUT_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# In-memory job store (sufficient for a single-process demo)
# ---------------------------------------------------------------------------

_jobs: Dict[str, Dict[str, Any]] = {}

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="DocNarratorAvatar", version="1.0.0")
app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/", include_in_schema=False)
async def frontend() -> FileResponse:
    return FileResponse(os.path.join(_STATIC_DIR, "index.html"))


@app.post("/api/process", summary="ドキュメントをアップロードして処理を開始する")
async def process_document(
    background_tasks: BackgroundTasks,
    file: UploadFile,
) -> Dict[str, str]:
    """Accept an uploaded document, persist it and start the processing pipeline.

    Returns a ``job_id`` that the client can use for status polling.
    """
    job_id = str(uuid.uuid4())

    # Persist the uploaded file
    filename: str = file.filename or "document"
    file_path = os.path.join(_UPLOAD_DIR, f"{job_id}_{filename}")
    content = await file.read()
    with open(file_path, "wb") as fh:
        fh.write(content)

    _jobs[job_id] = {
        "status": "processing",
        "progress": 0,
        "step": "ファイルを受信しました",
        "filename": filename,
    }

    background_tasks.add_task(_run_pipeline, job_id, file_path, filename)
    logger.info("ジョブ開始: %s (%s)", job_id, filename)
    return {"job_id": job_id}


@app.get("/api/status/{job_id}", summary="処理状態を取得する")
async def get_status(job_id: str) -> Dict[str, Any]:
    _require_job(job_id)
    job = _jobs[job_id]
    return {
        "status": job["status"],
        "progress": job.get("progress", 0),
        "step": job.get("step", ""),
        "error": job.get("error"),
    }


@app.get("/api/result/{job_id}", summary="処理結果を取得する")
async def get_result(job_id: str) -> Dict[str, Any]:
    _require_job(job_id)
    job = _jobs[job_id]

    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="処理が完了していません")

    return {
        "video_url": f"/api/video/{job_id}",
        "captions": job.get("captions", []),
        "script": job.get("script", ""),
        "has_video": job.get("has_video", False),
    }


@app.get("/api/video/{job_id}", summary="生成した動画を取得する")
async def get_video(job_id: str) -> FileResponse:
    _require_job(job_id)
    video_path: str = _jobs[job_id].get("video_path", "")

    if not video_path or not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="動画ファイルが見つかりません")

    return FileResponse(video_path, media_type="video/mp4", filename="avatar.mp4")


# ---------------------------------------------------------------------------
# Background pipeline
# ---------------------------------------------------------------------------


async def _run_pipeline(job_id: str, file_path: str, filename: str) -> None:
    """Full processing pipeline executed in the background."""
    from services.document import DocumentProcessor
    from services.ai import AIService
    from services.avatar import AvatarService

    try:
        doc_processor = DocumentProcessor()
        ai_service = AIService()
        avatar_service = AvatarService()
        loop = asyncio.get_event_loop()

        # Step 1 – extract text from document
        _update(job_id, progress=10, step="ドキュメントを処理中...")
        text, _images = await loop.run_in_executor(
            None, doc_processor.process, file_path, filename
        )
        logger.info("テキスト抽出完了: %d 文字 (%s)", len(text), filename)

        # Step 2 – generate script & captions with Azure OpenAI
        _update(job_id, progress=35, step="AI でスクリプトとキャプションを生成中...")
        script, captions = await ai_service.generate_script_and_captions(text)
        _jobs[job_id]["script"] = script
        _jobs[job_id]["captions"] = captions
        logger.info(
            "スクリプト生成完了: %d 文字, キャプション %d 件",
            len(script), len(captions),
        )

        # Step 3 – generate avatar video with Azure AI Speech
        _update(job_id, progress=60, step="アバター動画を生成中...")
        video_path = os.path.join(_OUTPUT_DIR, f"{job_id}.mp4")
        has_video = await avatar_service.generate_video(script, video_path)

        if has_video:
            _jobs[job_id]["video_path"] = video_path
            _jobs[job_id]["has_video"] = True
        else:
            _jobs[job_id]["has_video"] = False

        _update(job_id, progress=100, step="完了しました！", status="completed")
        logger.info("ジョブ完了: %s", job_id)

    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("パイプラインエラー: %s", job_id)
        _jobs[job_id].update(
            {
                "status": "failed",
                "error": str(exc),
                "step": f"エラーが発生しました: {exc}",
            }
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require_job(job_id: str) -> None:
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="ジョブが見つかりません")


def _update(job_id: str, **kwargs: Any) -> None:
    _jobs[job_id].update(kwargs)
