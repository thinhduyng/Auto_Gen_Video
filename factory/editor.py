"""Persistent Remotion revisions, separate from disposable engine render directories."""

import copy
import json
import re
import subprocess
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from .config import RUNS_DIR
from .editor_models import assemble, select_scenes, validate_plan

_lock = threading.RLock()
_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='editor')
ACTIVE = {'queued', 'importing', 'interpreting', 'preparing', 'rendering'}


def read_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)


def safe_id(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,160}', value):
        raise ValueError('ID không hợp lệ.')
    return value


def root(job_id: str) -> Path:
    path = (RUNS_DIR / safe_id(job_id)).resolve()
    if path.parent != RUNS_DIR.resolve() or not (path / 'job.json').is_file():
        raise ValueError('Không tìm thấy video.')
    return path / 'editor'


def revision_dir(job_id: str, rid: str) -> Path:
    return root(job_id) / 'revisions' / safe_id(rid)


def revision(job_id: str, rid: str) -> dict:
    return read_json(revision_dir(job_id, rid) / 'revision.json')


def update(job_id: str, rid: str, **fields) -> dict:
    with _lock:
        path = revision_dir(job_id, rid) / 'revision.json'
        info = read_json(path)
        info.update(fields)
        write_json(path, info)
        return info


def _enqueue(fn, *args):
    return _pool.submit(fn, *args)


def bootstrap(job_id: str) -> dict:
    with _lock:
        folder = root(job_id)
        if not (folder / 'state.json').exists():
            job = read_json(folder.parent / 'job.json')
            if job.get('engines', {}).get('remotion', {}).get('status') != 'done':
                raise ValueError('Cần một video Remotion đã dựng xong.')
            write_json(folder / 'state.json', {'current': 'baseline', 'requests': {}})
            write_json(folder / 'revisions/baseline/revision.json', {
                'id': 'baseline', 'parent': None, 'status': 'queued', 'summary': 'Video gốc',
                'created': datetime.now().isoformat(timespec='seconds')})
            _enqueue(_import, job_id)
        return state(job_id)


def state(job_id: str) -> dict:
    folder = root(job_id)
    result = read_json(folder / 'state.json')
    result['revisions'] = [read_json(p) for p in sorted((folder / 'revisions').glob('*/revision.json'))]
    result['revisions'].sort(key=lambda r: r.get('created', ''))
    return result


def detail(job_id: str, rid: str) -> dict:
    info = revision(job_id, rid)
    path = revision_dir(job_id, rid) / 'bundle.json'
    if path.exists():
        b = read_json(path)
        data = assemble(b['bundles'], b['meta'], b['diagrams'])
        info['duration'] = data['duration']
        info['scenes'] = [dict(s, say=b['bundles'][i]['source']['say']) for i, s in enumerate(data['scenes'])]
    return info


def _import(job_id: str) -> None:
    try:
        update(job_id, 'baseline', status='importing', message='Khôi phục hình và giọng gốc')
        from .editor_media import import_baseline
        import_baseline(job_id)
        update(job_id, 'baseline', status='ready', message='Sẵn sàng')
    except Exception as exc:
        _fail(job_id, 'baseline', exc)


class EditRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    parent: str
    start: float = Field(ge=0, allow_inf_nan=False)
    end: float = Field(gt=0, allow_inf_nan=False)
    prompt: str = Field(min_length=2, max_length=6000)
    request_id: str = Field(min_length=1, max_length=100)
    assets: list[str] = Field(default_factory=list, max_length=4)


def submit(job_id: str, raw: dict) -> dict:
    req = EditRequest.model_validate(raw)
    if not req.prompt.strip():
        raise ValueError('Cần mô tả thay đổi.')
    with _lock:
        folder = root(job_id)
        st = state(job_id)
        if req.request_id in st['requests']:
            return revision(job_id, st['requests'][req.request_id])
        if req.parent != st['current']:
            raise ValueError('Phiên bản hiện tại đã đổi; hãy tải lại trình chỉnh sửa.')
        if revision(job_id, req.parent)['status'] != 'ready':
            raise ValueError('Phiên bản nguồn chưa sẵn sàng.')
        if any(r['status'] in ACTIVE for r in st['revisions']):
            raise ValueError('Đang có chỉnh sửa chạy; hãy đợi hoàn tất.')
        parent = read_json(revision_dir(job_id, req.parent) / 'bundle.json')
        data = assemble(parent['bundles'], parent['meta'], parent['diagrams'])
        selected = select_scenes(data['scenes'], req.start, req.end)
        for aid in req.assets:
            asset(job_id, aid)
        rid = uuid.uuid4().hex
        info = {'id': rid, 'parent': req.parent, 'status': 'queued', 'summary': req.prompt[:200],
                'created': datetime.now().isoformat(timespec='seconds'), 'selected': selected}
        write_json(revision_dir(job_id, rid) / 'revision.json', info)
        write_json(revision_dir(job_id, rid) / 'request.json', req.model_dump())
        st['requests'][req.request_id] = rid
        st.pop('revisions', None)
        write_json(folder / 'state.json', st)
        _enqueue(_process, job_id, rid)
        return info


def _fail(job_id: str, rid: str, exc: Exception):
    # Only controlled errors reach the UI; provider/library exceptions can contain secrets.
    from .config import setting
    message = str(exc)[:1000] if isinstance(exc, (ValueError, RuntimeError)) else 'Xử lý lỗi; kiểm tra cấu hình hoặc thử lại.'
    for key_name in ('EDITOR_LLM_API_KEY', 'GEMINI_API_KEY', 'VIENEU_API_KEY'):
        secret = setting(key_name)
        if secret:
            message = message.replace(secret, '[redacted]')
    update(job_id, rid, status='failed', message=message)


def _process(job_id: str, rid: str):
    try:
        folder = revision_dir(job_id, rid)
        req = read_json(folder / 'request.json')
        parent = read_json(revision_dir(job_id, req['parent']) / 'bundle.json')
        selected = revision(job_id, rid)['selected']
        imgs = [asset(job_id, aid) for aid in req['assets']]
        plan_path = folder / 'plan.json'
        if plan_path.exists():
            raw = read_json(plan_path)
        else:
            from .editor_llm import interpret
            update(job_id, rid, status='interpreting', message='Qwen đang đọc yêu cầu')
            chosen = [dict(b['source'], id=b['id'], animation=b.get('animation', 'default'),
                           duration=b['duration']) for b in parent['bundles'] if b['id'] in selected]
            positions = [i for i, b in enumerate(parent['bundles']) if b['id'] in selected]
            context = [b['source'] for i, b in enumerate(parent['bundles'])
                       if i in (positions[0] - 1, positions[-1] + 1)]
            raw = interpret(req['prompt'], chosen, context, imgs, parent['meta'])
            try:
                validate_plan(raw, parent['bundles'], selected, set(req['assets']))
            except ValueError:
                raw = interpret(req['prompt'], chosen, context, imgs, parent['meta'],
                                repair='Previous response failed scene/schema/scope/cue validation. Return a valid complete plan.')
            plan = validate_plan(raw, parent['bundles'], selected, set(req['assets']))
            write_json(plan_path, plan.model_dump())
        plan = validate_plan(raw, parent['bundles'], selected, set(req['assets']))
        update(job_id, rid, status='preparing', summary=plan.summary, message='Chuẩn bị cảnh và giọng đọc')
        from .editor_media import prepare_revision, render_revision
        if not (folder / 'bundle.json').exists():
            prepare_revision(job_id, rid, parent, selected, plan)
        update(job_id, rid, status='rendering', message='Remotion đang dựng bản xem thử')
        render_revision(job_id, rid)
        info = detail(job_id, rid)
        update(job_id, rid, status='ready', message='Sẵn sàng xem thử', duration=info['duration'])
    except Exception as exc:
        _fail(job_id, rid, exc)


def retry(job_id: str, rid: str) -> dict:
    with _lock:
        if revision(job_id, rid)['status'] != 'failed':
            raise ValueError('Chỉ thử lại phiên bản bị lỗi.')
        if any(r['status'] in ACTIVE for r in state(job_id)['revisions']):
            raise ValueError('Đang có tác vụ chỉnh sửa khác.')
        info = update(job_id, rid, status='queued', message='Đang chờ thử lại')
        _enqueue(_import if rid == 'baseline' else _process, *([job_id] if rid == 'baseline' else [job_id, rid]))
        return info


def accept(job_id: str, rid: str, expected_current: str) -> dict:
    with _lock:
        st = state(job_id)
        if st['current'] != expected_current:
            raise ValueError('Phiên bản đã đổi; hãy tải lại.')
        if revision(job_id, rid)['status'] != 'ready':
            raise ValueError('Phiên bản chưa sẵn sàng.')
        if any(r['status'] in ACTIVE for r in st['revisions']):
            raise ValueError('Hãy đợi tác vụ đang chạy trước khi đổi phiên bản.')
        st['current'] = rid
        st.pop('revisions', None)
        write_json(root(job_id) / 'state.json', st)
        return state(job_id)


def discard(job_id: str, rid: str):
    with _lock:
        if rid == 'baseline' or rid == state(job_id)['current'] or revision(job_id, rid)['status'] in ACTIVE:
            raise ValueError('Không thể bỏ phiên bản gốc, hiện tại hoặc đang xử lý.')
        return update(job_id, rid, status='discarded')


def asset(job_id: str, aid: str) -> dict:
    folder = root(job_id)
    path = folder / 'assets' / (safe_id(aid) + '.json')
    if not path.exists():
        raise ValueError('Không tìm thấy ảnh đã tải lên.')
    info = read_json(path)
    info['path'] = str(folder / 'assets' / (aid + '.jpg'))
    return info


def upload(job_id: str, data: bytes, name: str) -> dict:
    if not 100 <= len(data) <= 8 * 1024 * 1024:
        raise ValueError('Ảnh cần từ 100 byte đến 8 MB.')
    folder = root(job_id) / 'assets'
    folder.mkdir(parents=True, exist_ok=True)
    aid = uuid.uuid4().hex
    temp, out = folder / (aid + '.upload'), folder / (aid + '.jpg')
    temp.write_bytes(data)
    try:
        p = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'stream=codec_name,width,height',
                            '-of', 'json', str(temp)], capture_output=True, timeout=15, check=True)
        streams = json.loads(p.stdout)['streams']
        s = streams[0]
        if len(streams) != 1 or s['codec_name'] not in ('png', 'mjpeg', 'webp') or not 0 < s['width'] * s['height'] <= 16000000:
            raise ValueError()
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(temp), '-frames:v', '1',
                        '-vf', 'scale=1600:1600:force_original_aspect_ratio=decrease', '-q:v', '3', str(out)],
                       capture_output=True, timeout=30, check=True)
        info = {'id': aid, 'name': Path(name).name[:150]}
        write_json(folder / (aid + '.json'), info)
        return info
    except (subprocess.SubprocessError, ValueError, KeyError, IndexError):
        out.unlink(missing_ok=True)
        raise ValueError('Chỉ nhận ảnh JPEG, PNG hoặc WebP hợp lệ, tối đa 16 triệu pixel.') from None
    finally:
        temp.unlink(missing_ok=True)


def recover_interrupted():
    for path in RUNS_DIR.glob('*/editor/revisions/*/revision.json'):
        info = read_json(path)
        if info.get('status') in ACTIVE:
            info.update(status='failed', message='Tác vụ bị gián đoạn; có thể thử lại.')
            write_json(path, info)
