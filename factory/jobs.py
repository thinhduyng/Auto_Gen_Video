"""Job = một nội dung cần làm video; mỗi engine là một tác vụ render chạy nền.

runs/<job_id>/job.json     trạng thái từng engine
runs/<job_id>/spec.json    bản chụp kịch bản lúc tạo job
runs/<job_id>/<engine>/    video.mp4, thumb.jpg, log.txt
publish/<job_id>/          video được chọn + caption.txt
"""

import json
import shutil
import subprocess
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from .config import MAX_PARALLEL, PUBLISH_DIR, RUNS_DIR
from .engines import ENGINES
from .spec import Spec, caption_text, slugify

_lock = threading.RLock()
_pool = ThreadPoolExecutor(max_workers=MAX_PARALLEL, thread_name_prefix="render")


def _job_dir(job_id: str) -> Path:
    d = (RUNS_DIR / job_id).resolve()
    if RUNS_DIR.resolve() not in d.parents:
        raise ValueError("job id không hợp lệ")
    return d


def load_job(job_id: str) -> dict:
    return json.loads((_job_dir(job_id) / "job.json").read_text(encoding="utf-8"))


def _save(job: dict) -> None:
    path = _job_dir(job["id"]) / "job.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _update(job_id: str, engine: str, **fields) -> None:
    with _lock:
        job = load_job(job_id)
        job["engines"][engine].update(fields)
        _save(job)


def list_jobs() -> list[dict]:
    jobs = []
    for f in RUNS_DIR.glob("*/job.json"):
        try:
            jobs.append(json.loads(f.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return sorted(jobs, key=lambda j: j["created"], reverse=True)


def create_job(spec: Spec, engines: list[str]) -> dict:
    engines = [e for e in ENGINES if e in engines] or list(ENGINES)
    job_id = f"{datetime.now():%Y%m%d-%H%M%S}-{slugify(spec.id or spec.title, 36)}"
    d = RUNS_DIR / job_id
    d.mkdir(parents=True)
    (d / "spec.json").write_text(json.dumps(spec.dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    job = {
        "id": job_id, "title": spec.title, "spec_id": spec.id, "created": datetime.now().isoformat(timespec="seconds"),
        "selected": None, "published": None,
        "engines": {e: {"status": "queued"} for e in engines},
    }
    _save(job)
    for e in engines:
        _pool.submit(_render, job_id, e)
    return job


def rerun(job_id: str, engine: str) -> None:
    if engine not in ENGINES:
        raise ValueError(f"không có engine {engine}")
    if (_job_dir(job_id) / "editor" / "state.json").exists() and engine == "remotion":
        raise ValueError("Video đã có lịch sử chỉnh sửa; dùng trình chỉnh sửa để giữ các phiên bản.")
    with _lock:
        job = load_job(job_id)
        job["engines"][engine] = {"status": "queued"}
        _save(job)
    _pool.submit(_render, job_id, engine)


def _render(job_id: str, key: str) -> None:
    engine = ENGINES[key]
    workdir = _job_dir(job_id) / key
    if workdir.exists():
        shutil.rmtree(workdir, ignore_errors=True)
    workdir.mkdir(parents=True)
    log_file = workdir / "log.txt"

    def log(msg: str) -> None:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now():%H:%M:%S}] {msg}\n")
        _update(job_id, key, message=msg[:200])

    t0 = time.time()
    _update(job_id, key, status="running", started=datetime.now().isoformat(timespec="seconds"), message="đang chuẩn bị")
    try:
        ok, why = engine.check()
        if not ok:
            raise RuntimeError(why)
        spec = Spec.model_validate(json.loads((_job_dir(job_id) / "spec.json").read_text(encoding="utf-8")))
        video = engine.render(spec, workdir, log)
        if video != workdir / "video.mp4":
            shutil.copy2(video, workdir / "video.mp4")
        _thumbnail(workdir / "video.mp4", workdir / "thumb.jpg")
        _update(job_id, key, status="done", seconds=round(time.time() - t0), message="xong",
                duration=_probe(workdir / "video.mp4"))
    except Exception as exc:  # hiện lỗi lên giao diện, chi tiết nằm trong log.txt
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(traceback.format_exc())
        _update(job_id, key, status="failed", seconds=round(time.time() - t0), message=str(exc)[-600:])


def _thumbnail(video: Path, out: Path) -> None:
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "2.5", "-i", str(video), "-frames:v", "1",
                    "-vf", "scale=360:-2", str(out)], check=False)


def _probe(video: Path) -> float | None:
    p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)],
                       capture_output=True, text=True)
    try:
        return round(float(p.stdout.strip()), 1)
    except ValueError:
        return None


def select(job_id: str, engine: str, revision_id: str | None = None) -> dict:
    """Chép video được chọn ra publish/<job_id>/ kèm caption.txt."""
    with _lock:
        job = load_job(job_id)
        info = job["engines"].get(engine)
        if not info or info.get("status") != "done":
            raise ValueError("engine này chưa có video hoàn chỉnh")
        spec = Spec.model_validate(json.loads((_job_dir(job_id) / "spec.json").read_text(encoding="utf-8")))
        out_dir = PUBLISH_DIR / job_id
        shutil.rmtree(out_dir, ignore_errors=True)
        out_dir.mkdir(parents=True)
        name = slugify(f"{spec.series or ''} {spec.ep or ''} {spec.title}", 70)
        video = out_dir / f"{name}.mp4"
        source = _job_dir(job_id) / engine / "video.mp4"
        if revision_id is not None:
            from . import editor
            if engine != "remotion" or editor.revision(job_id, revision_id)["status"] != "ready":
                raise ValueError("Phiên bản chưa sẵn sàng.")
            source = editor.revision_dir(job_id, revision_id) / "video.mp4"
        shutil.copy2(source, video)
        caption = caption_text(spec)
        credits = _job_dir(job_id) / engine / "credits.txt"   # ảnh Wikimedia Commons: ghi nguồn theo giấy phép
        if credits.exists():
            caption += "\n\n" + credits.read_text(encoding="utf-8").strip()
        (out_dir / "caption.txt").write_text(caption, encoding="utf-8")
        job["selected"] = engine
        job["published"] = {"video": str(video), "caption": caption, "at": datetime.now().isoformat(timespec="seconds"), "revision": revision_id}
        _save(job)
        return job


def recover_interrupted() -> None:
    """Sau khi khởi động lại, tác vụ đang chạy dở bị đánh dấu lỗi để bấm chạy lại."""
    for job in list_jobs():
        changed = False
        for info in job["engines"].values():
            if info.get("status") in ("queued", "running"):
                info.update(status="failed", message="bị gián đoạn do server khởi động lại, bấm Chạy lại")
                changed = True
        if changed:
            _save(job)
