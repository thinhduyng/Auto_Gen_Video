"""HTTP endpoints for the scene editor; raw uploads avoid a multipart dependency."""

from functools import wraps

from fastapi import APIRouter, Body, HTTPException, Request
from pydantic import ValidationError

from . import editor

router = APIRouter(prefix='/api/jobs/{job_id}/editor')


def errors(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except ValidationError:
            raise HTTPException(422, 'Yêu cầu chỉnh sửa không hợp lệ.') from None
        except (ValueError, FileNotFoundError) as exc:
            raise HTTPException(400, str(exc) if isinstance(exc, ValueError) else 'Không tìm thấy phiên bản.') from None
    return wrapped


@router.post('')
@errors
def bootstrap(job_id: str):
    return editor.bootstrap(job_id)


@router.get('')
@errors
def state(job_id: str):
    return editor.state(job_id)


@router.get('/revisions/{rid}')
@errors
def revision(job_id: str, rid: str):
    return editor.detail(job_id, rid)


@router.post('/revisions', status_code=202)
@errors
def submit(job_id: str, body: dict = Body(...)):
    return editor.submit(job_id, body)


@router.post('/revisions/{rid}/accept')
@errors
def accept(job_id: str, rid: str, body: dict = Body(...)):
    return editor.accept(job_id, rid, body.get('expected_current', ''))


@router.post('/revisions/{rid}/retry')
@errors
def retry(job_id: str, rid: str):
    return editor.retry(job_id, rid)


@router.post('/revisions/{rid}/discard')
@errors
def discard(job_id: str, rid: str):
    return editor.discard(job_id, rid)


@router.post('/revisions/{rid}/publish')
@errors
def publish(job_id: str, rid: str):
    from .jobs import select
    if editor.revision(job_id, rid)['status'] != 'ready':
        raise ValueError('Phiên bản chưa sẵn sàng.')
    return select(job_id, 'remotion', revision_id=rid)


@router.post('/images')
async def upload(job_id: str, request: Request, name: str = 'image'):
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > 8 * 1024 * 1024:
            raise HTTPException(413, 'Ảnh vượt quá 8 MB.')
    try:
        # Image decoding runs off the event loop.
        from starlette.concurrency import run_in_threadpool
        return await run_in_threadpool(editor.upload, job_id, bytes(data), name)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
