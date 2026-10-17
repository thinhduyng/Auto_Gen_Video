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
    stock_query: str | None = Field(default=None, min_length=2, max_length=200)
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
        if r.image_asset_id and r.stock_query:
            raise ValueError('Chỉ chọn ảnh tải lên hoặc ảnh stock cho mỗi cảnh.')
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
                if k in ('src', 'url', 'path', '__html', 'code') or (k == 'style' and v not in ('solid', 'flow', 'blocked')):
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
    for key in ('heading','title','sub','tag','question','answer','label','kicker','q_label','a_label'):
        if key in scene and not isinstance(scene[key],str):
            raise ValueError('Chữ hiển thị phải là chuỗi.')
    if 'headline' in scene:
        h=scene['headline']
        if not isinstance(h,list) or not 1 <= len(h) <= 12 or any(
            not isinstance(x,list) or len(x)!=2 or not isinstance(x[0],str) or not isinstance(x[1],bool) for x in h):
            raise ValueError('headline cần danh sách [chữ, tô màu].')
    for key, required in (('items',('text',)),('chips',('text',)),('stats',('value','label'))):
        if key in scene:
            values=scene[key]
            if not isinstance(values,list) or len(values)>8 or any(not isinstance(x,dict) or
                any(not isinstance(x.get(k),(str,int,float)) for k in required) for x in values):
                raise ValueError('Danh sách chữ/số không hợp lệ hoặc quá nhiều mục.')
    for side in ('left','right'):
        if side in scene:
            obj=scene[side]
            if not isinstance(obj,dict) or not isinstance(obj.get('title'),str) or not isinstance(obj.get('points',[]),list) or any(
                not isinstance(v,str) for v in obj.get('points',[])):
                raise ValueError('Cột so sánh cần tiêu đề và danh sách chuỗi.')



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
            if b['animation'] == 'stagger':
                for field in ('items', 'stats', 'chips'):
                    for n, item in enumerate(s.get(field, [])):
                        if isinstance(item, dict):
                            item['t'] = min(end - 1 / FPS, start + .15 + n * min(.45, (end-start)/max(2,len(s[field])+1)))

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
