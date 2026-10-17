"""Validated scene edits and scene-local timeline arithmetic (no provider or I/O)."""

import copy
import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .spec import Scene

FPS = 30


class Replacement(BaseModel):
    model_config = ConfigDict(extra='forbid')
    source_id: str | None = None
    scene: dict | None = None
    image_asset_id: str | None = None
    animation: Literal['default', 'fade', 'slide', 'zoom', 'stagger'] | None = None
    hold_seconds: float | None = Field(default=None, ge=0, le=15, allow_inf_nan=False)


class EditPlan(BaseModel):
    model_config = ConfigDict(extra='forbid')
    summary: str = Field(min_length=1, max_length=2000)
    replacements: list[Replacement] = Field(min_length=1, max_length=20)


def select_scenes(scenes: list[dict], start: float, end: float) -> list[str]:
    if not scenes or not all(math.isfinite(x) for x in (start, end)) or not 0 <= start < end <= scenes[-1]['end'] + 1e-6:
        raise ValueError('Khoảng thời gian không hợp lệ.')
    return [s['id'] for s in scenes if s['start'] < end and s['end'] > start]


def validate_plan(raw: dict, bundles: list[dict], selected: list[str], assets: set[str]) -> EditPlan:
    plan = EditPlan.model_validate(raw)
    sources = {b['id']: b['source'] for b in bundles}
    if not selected or any(s not in sources for s in selected):
        raise ValueError('Cảnh đã chọn không tồn tại.')
    for r in plan.replacements:
        if r.source_id is not None and r.source_id not in selected:
            raise ValueError('Qwen đề xuất thay đổi ngoài các cảnh đã chọn.')
        if r.image_asset_id is not None and r.image_asset_id not in assets:
            raise ValueError('Ảnh thay thế không thuộc yêu cầu này.')
        if r.scene is None and r.source_id is None:
            raise ValueError('Cảnh mới cần đầy đủ nội dung và lời đọc.')
        if r.scene is not None:
            validate_scene(r.scene)
            Scene.model_validate(r.scene)
    return plan


# Only canonical presentation data may enter the renderer, never file/HTML/code settings.
SCENE_FIELDS = {'type', 'say', 'tag', 'headline', 'sub', 'chips', 'heading', 'items', 'left', 'right',
                'stats', 'question', 'answer', 'answer_cue', 'label', 'q_label', 'a_label', 'title',
                'kicker', 'nodes', 'edges', 'groups', 'steps', 'stock', 'diagram', 'events', 'flow'}


def validate_scene(scene: dict) -> None:
    if set(scene) - SCENE_FIELDS:
        raise ValueError('Cảnh chứa trường không được hỗ trợ.')
    say = scene.get('say', '')
    if not isinstance(say, str) or not 2 <= len(say) <= 5000:
        raise ValueError('Lời đọc cần từ 2 đến 5000 ký tự.')
    def walk(node, depth=0):
        if depth > 12:
            raise ValueError('Nội dung cảnh quá phức tạp.')
        if isinstance(node, dict):
            for k, v in node.items():
                if k in ('src', 'url', 'path', '__html', 'style', 'code'):
                    raise ValueError('Cảnh chứa tham chiếu hoặc mã không được hỗ trợ.')
                if k in ('cue', 'answer_cue') and v and v not in say:
                    raise ValueError('Cue phải trích nguyên văn từ lời đọc của cảnh.')
                walk(v, depth + 1)
        elif isinstance(node, list):
            if len(node) > 60:
                raise ValueError('Danh sách nội dung quá dài.')
            for v in node:
                walk(v, depth + 1)
        elif isinstance(node, str) and len(node) > (5000 if node == say else 1000):
            raise ValueError('Chữ hiển thị quá dài.')
        elif isinstance(node, float) and not math.isfinite(node):
            raise ValueError('Số không hợp lệ.')
    walk(scene)


def shift_scene(scene: dict, offset: float) -> dict:
    def walk(node):
        if isinstance(node, list):
            return [walk(x) for x in node]
        if isinstance(node, dict):
            return {k: round(v + offset, 6) if k in ('t', 'start', 'end', 'audio_at', 'answer_t')
                    and isinstance(v, (int, float)) else walk(v) for k, v in node.items()}
        return node
    return walk(copy.deepcopy(scene))


def assemble(bundles: list[dict], meta: dict, diagrams: dict) -> dict:
    data = {'meta': copy.deepcopy(meta), 'scenes': [], 'words': [], 'phrases': [],
            'beats': [], 'diagrams': copy.deepcopy(diagrams)}
    frame = 0
    for i, b in enumerate(bundles):
        start = frame / FPS
        frame += max(1, math.ceil(b['duration'] * FPS - 1e-7))
        end = frame / FPS
        s = shift_scene(b['scene'], start)
        s.update(id=b['id'], start=start, end=end)
        if b.get('animation'):
            s['animation'] = b['animation']
        data['scenes'].append(s)
        base = len(data['words'])
        for w in b['words']:
            data['words'].append(dict(w, start=round(w['start'] + start, 6), end=round(w['end'] + start, 6)))
        # Caption phrase indices are scene-local; never let phrases cross a scene boundary.
        for p in b.get('phrases', []):
            data['phrases'].append(dict(p, **{'from': p['from'] + base, 'to': p['to'] + base},
                                        start=p['start'] + start, end=p['end'] + start))
        for j, beat in enumerate(b['beats']):
            data['beats'].append(dict(beat, scene=i, t0=beat['t0'] + start,
                                     t1=end if j == len(b['beats']) - 1 else min(end, beat['t1'] + start)))
    data['duration'] = frame / FPS
    return data
