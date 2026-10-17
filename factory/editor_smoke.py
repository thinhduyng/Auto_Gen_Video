"""Opt-in live Qwen/editor check, using .env without printing credentials.

python -m factory.editor_smoke --job JOB_ID --api-only
python -m factory.editor_smoke --job JOB_ID --render
"""

import argparse
import json
import time
import uuid

from . import editor
from .editor_llm import interpret
from .editor_models import assemble, select_scenes, validate_plan


def wait(job_id: str, rid: str) -> dict:
    previous = None
    while True:
        info = editor.revision(job_id, rid)
        if info['status'] != previous:
            print(info['status'], flush=True)
            previous = info['status']
        if info['status'] == 'failed':
            raise RuntimeError(info.get('message', 'Editor failed'))
        if info['status'] == 'ready':
            return info
        time.sleep(.5)


def main():
    parser = argparse.ArgumentParser(description='Check Qwen editing or render a preview; never publish automatically.')
    parser.add_argument('--job', required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--api-only', action='store_true')
    mode.add_argument('--render', action='store_true')
    parser.add_argument('--start', type=float, default=0)
    parser.add_argument('--end', type=float, default=5)
    parser.add_argument('--prompt', default='Chỉ đổi tiêu đề trên màn hình thành “Origami mở ra tương lai”. Giữ nguyên lời đọc và hình nền.')
    args = parser.parse_args()
    try:
        state = editor.bootstrap(args.job)
        baseline = editor.revision(args.job, 'baseline')
        if baseline['status'] == 'failed':
            editor.retry(args.job, 'baseline')
        wait(args.job, 'baseline')
        parent = state['current']
        source = editor.read_json(editor.revision_dir(args.job, parent) / 'bundle.json')
        data = assemble(source['bundles'], source['meta'], source['diagrams'])
        selected = select_scenes(data['scenes'], args.start, args.end)
        if args.api_only:
            scenes = [dict(b['source'], id=b['id']) for b in source['bundles'] if b['id'] in selected]
            raw = interpret(args.prompt, scenes, [], [], source['meta'])
            plan = validate_plan(raw, source['bundles'], selected, set(), source['diagrams'])
            print('Qwen returned a validated edit plan:')
            print(json.dumps(plan.model_dump(), ensure_ascii=False, indent=2))
        else:
            info = editor.submit(args.job, {'parent': parent, 'start': args.start, 'end': args.end,
                                          'prompt': args.prompt, 'request_id': uuid.uuid4().hex})
            wait(args.job, info['id'])
            print('Preview:', editor.revision_dir(args.job, info['id']) / 'video.mp4')
            print('The original/current/published video has not been replaced.')
    except (ValueError, RuntimeError) as exc:
        print('Check failed:', str(exc))
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
