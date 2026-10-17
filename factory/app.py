"""Server của video-factory: giao diện chọn video + API.

    python3 chay-web.py   (hoặc: python3 vf-python.py -m uvicorn factory.app:app --port 8600)
"""

import json
import shutil
import threading
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from . import jobs, editor
from .config import CONTENT_DIR, PUBLISH_DIR, RUNS_DIR, WEB_DIR
from .engines import ENGINES
from .spec import Spec, slugify


@asynccontextmanager
async def lifespan(_app: FastAPI):
    jobs.recover_interrupted()
    editor.recover_interrupted()
    yield


app = FastAPI(title="Video Factory", lifespan=lifespan)
from .editor_api import router as editor_router
app.include_router(editor_router)
app.mount("/runs", StaticFiles(directory=RUNS_DIR), name="runs")
app.mount("/publish", StaticFiles(directory=PUBLISH_DIR), name="publish")
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(WEB_DIR / "index.html")


@app.get("/api/engines")
def engines():
    out = []
    for e in ENGINES.values():
        ok, why = e.check()
        out.append({"key": e.key, "label": e.label, "style": e.style, "ready": ok, "reason": why})
    return out


@app.get("/api/content")
def content_list():
    items = []
    for f in sorted(CONTENT_DIR.rglob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        items.append({"path": f.relative_to(CONTENT_DIR).as_posix(), "title": d.get("title", f.stem),
                      "series": d.get("series"), "ep": d.get("ep"), "scenes": len(d.get("scenes", []))})
    return items


def _content_file(path: str) -> Path:
    f = (CONTENT_DIR / path).resolve()
    if CONTENT_DIR.resolve() not in f.parents or f.suffix != ".json":
        raise HTTPException(400, "đường dẫn không hợp lệ")
    return f


@app.get("/api/content/{path:path}")
def content_get(path: str):
    f = _content_file(path)
    if not f.exists():
        raise HTTPException(404, "không có kịch bản này")
    return json.loads(f.read_text(encoding="utf-8"))


@app.put("/api/content/{path:path}")
def content_put(path: str, spec: dict = Body(...)):
    try:
        Spec.model_validate(spec)
    except ValidationError as exc:
        raise HTTPException(422, _errors(exc))
    f = _content_file(path)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "path": path}


_drafts: dict[str, dict] = {}


@app.post("/api/draft")
def draft(body: dict = Body(...)):
    """Viết nháp chạy nền (gói Gemini miễn phí có thể phải chờ); giao diện hỏi tiến độ qua GET /api/draft/{id}."""
    from .llm import draft_spec

    topic = (body.get("topic") or "").strip()
    if len(topic) < 4:
        raise HTTPException(400, "hãy nhập chủ đề cụ thể hơn")
    did = uuid.uuid4().hex[:10]
    job = _drafts[did] = {"status": "running", "log": [], "result": None, "error": None}

    def work():
        try:
            spec, path, issues = draft_spec(topic, body.get("level") or "medium", body.get("hook") or "auto",
                                            body.get("notes") or "", bool(body.get("check", True)), log=job["log"].append,
                                            podcast=bool(body.get("podcast")), tournament=bool(body.get("tournament")))
            job.update(status="done", result={"path": path, "spec": spec, "issues": issues})
        except Exception as exc:
            job.update(status="failed", error=f"Gemini chưa viết được nháp: {exc}")

    threading.Thread(target=work, daemon=True, name=f"draft-{did}").start()
    return {"id": did}


@app.get("/api/podcast/voices")
def podcast_voices():
    from . import eleven

    return {"configured": bool(eleven.api_key()), "voices": eleven.voices(), "default": eleven.DEFAULT_VOICE}


@app.get("/api/tts/vieneu/voices")
def vieneu_voices():
    from . import vieneu

    try:
        return {"ready": True, "voices": vieneu.voices(), "default": vieneu.default_voice()}
    except RuntimeError as exc:
        return {"ready": False, "voices": [], "default": vieneu.default_voice(), "reason": str(exc)}


@app.post("/api/podcast")
def podcast(body: dict = Body(...)):
    """Nhờ Gemini viết bản podcast (văn nói) cho kịch bản đang mở; chạy nền như viết nháp."""
    from .llm import podcast_version

    raw = body.get("spec")
    if not raw or not raw.get("scenes"):
        raise HTTPException(400, "cần kịch bản (spec) có cảnh")
    did = uuid.uuid4().hex[:10]
    job = _drafts[did] = {"status": "running", "log": [], "result": None, "error": None}

    def work():
        try:
            job.update(status="done", result={"podcast": podcast_version(raw, log=job["log"].append)})
        except Exception as exc:
            job.update(status="failed", error=f"Gemini chưa viết được bản podcast: {exc}")

    threading.Thread(target=work, daemon=True, name=f"podcast-{did}").start()
    return {"id": did}


# ---------- file giọng podcast làm sẵn (web ElevenLabs, tự thu…) ----------
AUDIO_DIR = CONTENT_DIR / "audio"
DOWNLOADS = Path.home() / "Downloads"
AUDIO_EXT = (".mp3", ".wav", ".m4a")


def _keep_audio(src: Path | bytes, stem: str, ext: str) -> str:
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    dst = AUDIO_DIR / f"{slugify(stem, 40)}-{datetime.now():%m%d-%H%M%S}{ext}"
    if isinstance(src, Path):
        shutil.copy2(src, dst)
    else:
        dst.write_bytes(src)
    return f"audio/{dst.name}"


@app.post("/api/podcast/watch")
def podcast_watch(body: dict = Body(...)):
    """Chờ file giọng mới xuất hiện trong Downloads (người dùng tự bấm Download trên web ElevenLabs) rồi lấy về."""
    since, stem = time.time(), body.get("name") or "podcast"
    did = uuid.uuid4().hex[:10]
    job = _drafts[did] = {"status": "running", "log": [], "result": None, "error": None}

    def work():
        while time.time() < since + 20 * 60:
            fresh = [f for f in DOWNLOADS.glob("*") if f.suffix.lower() in AUDIO_EXT and f.stat().st_mtime > since - 1]
            if fresh:
                f = max(fresh, key=lambda x: x.stat().st_mtime)
                size = f.stat().st_size
                time.sleep(1.5)   # đợi trình duyệt ghi xong
                if f.exists() and size > 0 and f.stat().st_size == size:
                    job.update(status="done", result={"audio": _keep_audio(f, stem, f.suffix.lower()), "source": f.name})
                    return
            time.sleep(2)
        job.update(status="failed", error="Sau 20 phút chưa thấy file giọng mới trong Downloads — dùng nút Tải file giọng lên")

    threading.Thread(target=work, daemon=True, name=f"watch-{did}").start()
    return {"id": did}


@app.post("/api/podcast/audio")
async def podcast_audio(request: Request, name: str = "podcast.mp3"):
    ext = Path(name).suffix.lower()
    if ext not in AUDIO_EXT:
        raise HTTPException(400, "chỉ nhận file mp3, wav hoặc m4a")
    data = await request.body()
    if not 1000 < len(data) < 200 * 1024 * 1024:
        raise HTTPException(400, "file giọng rỗng hoặc quá lớn")
    return {"audio": _keep_audio(data, Path(name).stem, ext)}


@app.get("/api/draft/{did}")
def draft_status(did: str):
    job = _drafts.get(did)
    if not job:
        raise HTTPException(404, "không có yêu cầu viết nháp này")
    return job


@app.post("/api/jobs")
def create(body: dict = Body(...)):
    raw = body.get("spec")
    if raw is None and body.get("content"):
        raw = json.loads(_content_file(body["content"]).read_text(encoding="utf-8"))
    if raw is None:
        raise HTTPException(400, "cần 'spec' hoặc 'content'")
    try:
        spec = Spec.model_validate(raw)
    except ValidationError as exc:
        raise HTTPException(422, _errors(exc))
    return jobs.create_job(spec, body.get("engines") or list(ENGINES))


@app.get("/api/jobs")
def job_list():
    return jobs.list_jobs()


@app.get("/api/jobs/{job_id}")
def job_get(job_id: str):
    try:
        return jobs.load_job(job_id)
    except (FileNotFoundError, ValueError):
        raise HTTPException(404, "không có job này")


@app.get("/api/jobs/{job_id}/log/{engine}")
def job_log(job_id: str, engine: str):
    f = RUNS_DIR / job_id / engine / "log.txt"
    if engine not in ENGINES or not f.exists():
        raise HTTPException(404, "chưa có log")
    lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
    return {"log": "\n".join(lines[-80:])}


@app.post("/api/jobs/{job_id}/rerun/{engine}")
def job_rerun(job_id: str, engine: str):
    try:
        jobs.rerun(job_id, engine)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True}


@app.post("/api/jobs/{job_id}/select/{engine}")
def job_select(job_id: str, engine: str):
    try:
        return jobs.select(job_id, engine)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


def _errors(exc: ValidationError) -> str:
    return "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()[:6])
