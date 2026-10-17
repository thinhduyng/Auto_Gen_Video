"""Remotion: motion graphics nền tối, phụ đề kiểu TikTok (project React ở engines/remotion-academic).

Giọng đọc và dòng thời gian dùng chung với engine HyperFrames (narration.build_timeline);
ảnh nền theo câu được đặt tạm vào public/jobs/ vì Remotion chỉ đọc file qua staticFile().

Remotion chỉ xuất khung hình JPEG (không kèm <Audio>), ffmpeg của hệ thống ghép thành video và gắn giọng đọc:
từ 01/10/2026 Smart App Control của Windows chặn avfilter-10.dll mà ffmpeg.exe/ffprobe.exe đi kèm Remotion nạp
(thoát mã 3236495362 = 0xC0E90002, "while piping frame 0" hoặc lúc đọc file audio).
"""

import json
import re
import shutil
import uuid
from pathlib import Path

from ..beats import attach as attach_beats
from ..config import CHROME, ENGINES_DIR
from ..narration import build_audio, build_timeline
from ..spec import Spec
from .base import Engine, Log, run, utf8_env

PROJECT = ENGINES_DIR / "remotion-academic"
CLI = PROJECT / "node_modules" / "@remotion" / "cli" / "remotion-cli.js"
FPS = 30                                                    # khớp src/index.tsx


class Remotion(Engine):
    key = "remotion"
    label = "Remotion"
    style = "Motion graphics nền tối trên ảnh đổi theo câu, phụ đề kiểu TikTok"

    def check(self):
        if not CLI.exists():
            return False, "chưa cài: chạy python3 cai-dat.py (npm ci trong engines/remotion-academic)"
        return True, ""

    def render(self, spec: Spec, workdir: Path, log: Log) -> Path:
        log(f"tạo giọng đọc {spec.tts_provider} và dòng thời gian từng từ")
        data, parts = build_timeline(spec, log)
        job = uuid.uuid4().hex[:12]
        beat_dir = PROJECT / "public" / "jobs" / job
        attach_beats(spec, data, beat_dir, f"jobs/{job}/", log, credits_out=workdir / "credits.txt")
        wav = workdir / "narration.wav"
        build_audio(parts, wav, data, spec.title)
        props = workdir / "props.json"
        props.write_text(json.dumps({"data": data, "audio": ""}, ensure_ascii=False), encoding="utf-8")
        from ..editor_media import capture_sources
        capture_sources(data, wav, beat_dir, workdir / "sources")
        # The pinned CLI interprets dots anywhere in sequence output paths as an extension.
        # Pass a relative path with no dots, including when workdir lives under .cache/.
        out, frames = workdir / "video.mp4", beat_dir / "frames"
        shutil.rmtree(frames, ignore_errors=True)
        log(f"Remotion render {data['duration']:.0f}s video")
        try:
            run(["node", CLI, "render", "src/index.tsx", "Academic", frames.relative_to(PROJECT), "--sequence", "--image-format=jpeg",
                 "--jpeg-quality=92", f"--props={props}", "--concurrency=8", f"--browser-executable={CHROME}", "--log=info"],
                cwd=PROJECT, log_file=workdir / "log.txt", env=utf8_env(REMOTION_DISABLE_TELEMETRY="1"), timeout=1800)
            first = re.fullmatch(r"(.*?)(\d+)\.jpe?g", min(f.name for f in frames.glob("*.jp*g")))
            log("ghép khung hình + giọng đọc bằng ffmpeg")
            run(["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), "-start_number", str(int(first[2])),
                 "-i", frames / f"{first[1]}%0{len(first[2])}d{Path(first[0]).suffix}", "-i", wav,
                 "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                 "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out],
                cwd=workdir, log_file=workdir / "log.txt")
        finally:
            wav.unlink(missing_ok=True)
            shutil.rmtree(beat_dir, ignore_errors=True)
            shutil.rmtree(frames, ignore_errors=True)
        return out


def render_prepared(data: dict, audio: Path, source_root: Path, workdir: Path, log: Log) -> Path:
    """Render a persistent revision, staging only trusted job-owned assets."""
    import copy
    prepared = copy.deepcopy(data)
    key = uuid.uuid4().hex[:12]
    stage = PROJECT / 'public' / 'jobs' / key
    frames = stage / 'frames'
    stage.mkdir(parents=True)
    try:
        for i, beat in enumerate(prepared.get('beats', [])):
            source = (source_root / beat['src']).resolve()
            if not source.is_relative_to(source_root.resolve()) or not source.is_file():
                raise ValueError('Không tìm thấy ảnh của cảnh.')
            name = f'b{i:03}{source.suffix.lower()}'
            shutil.copy2(source, stage / name)
            beat['src'] = f'jobs/{key}/{name}'
        props = workdir / 'props.json'
        props.write_text(json.dumps({'data': prepared, 'audio': ''}, ensure_ascii=False), encoding='utf-8')
        log('Dựng khung hình Remotion; thời lượng có thể thay đổi theo lời đọc')
        run(['node', CLI, 'render', 'src/index.tsx', 'Academic', frames.relative_to(PROJECT),
             '--sequence', '--image-format=jpeg', '--jpeg-quality=92', f'--props={props}',
             '--concurrency=2', f'--browser-executable={CHROME}', '--log=error'],
            cwd=PROJECT, log_file=workdir / 'render.log', env=utf8_env(REMOTION_DISABLE_TELEMETRY='1'), timeout=3600)
        first = re.fullmatch(r'(.*?)(\d+)\.jpe?g', min(f.name for f in frames.glob('*.jp*g')))
        out = workdir / 'video.mp4'
        run(['ffmpeg', '-v', 'error', '-y', '-framerate', str(FPS), '-start_number', str(int(first[2])),
             '-i', frames / f'{first[1]}%0{len(first[2])}d{Path(first[0]).suffix}', '-i', audio,
             '-map', '0:v', '-map', '1:a', '-c:v', 'libx264', '-preset', 'medium', '-crf', '18',
             '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', out],
            cwd=PROJECT, log_file=workdir / 'render.log', timeout=1800)
        run(['ffmpeg', '-v', 'error', '-y', '-ss', str(min(1, prepared['duration']/2)), '-i', out,
             '-frames:v', '1', '-vf', 'scale=360:-2', workdir / 'thumb.jpg'],
            cwd=PROJECT, log_file=workdir / 'render.log')
        return out
    finally:
        shutil.rmtree(stage, ignore_errors=True)
