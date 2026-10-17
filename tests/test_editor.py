import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from factory import editor_models as m


def bundle(sid='s1', duration=3):
    return {'id': sid, 'source': {'type': 'next', 'title': 'Hello', 'say': 'Xin chào.'},
            'duration': duration, 'scene': {'type': 'next', 'title': 'Hello', 'start': 0, 'end': duration,
            'audio_at': .15, 'events': [{'t': .5}]}, 'words': [{'display': 'Xin', 'start': .15, 'end': .7}],
            'beats': [{'t0': 0, 't1': duration, 'src': 'assets/a.jpg'}], 'audio': 'audio/s1.wav'}


class TimelineTests(unittest.TestCase):
    def test_half_open_selection_and_invalid_range(self):
        scenes = [{'id': 'a', 'start': 0, 'end': 3}, {'id': 'b', 'start': 3, 'end': 5}]
        self.assertEqual(m.select_scenes(scenes, 0, 3), ['a'])
        self.assertEqual(m.select_scenes(scenes, 2.9, 4), ['a', 'b'])
        for start, end in [(0, 0), (-1, 1), (1, 6), (float('nan'), 2)]:
            with self.assertRaises(ValueError):
                m.select_scenes(scenes, start, end)

    def test_duration_change_rebases_words_beats_cues_without_mutating_parent(self):
        a, b = bundle(), bundle('s2', 2)
        a['duration'] = 4
        old = copy.deepcopy(b)
        data = m.assemble([a, b], {'title': 'Test'}, {})
        self.assertEqual(data['duration'], 6)
        self.assertEqual(data['scenes'][1]['start'], 4)
        self.assertEqual(data['scenes'][1]['events'][0]['t'], 4.5)
        self.assertEqual(data['words'][1]['start'], 4.15)
        self.assertEqual(data['beats'][1]['t0'], 4)
        self.assertEqual(data['beats'][0]['t1'], 4)
        self.assertEqual(b, old)

    def test_plan_rejects_unknown_assets_and_out_of_scope(self):
        plan = {'summary': 'Change', 'replacements': [{'source_id': 'other'}]}
        with self.assertRaises(ValueError):
            m.validate_plan(plan, [bundle()], ['s1'], set())
        plan['replacements'] = [{'source_id': 's1', 'image_asset_id': 'unknown'}]
        with self.assertRaises(ValueError):
            m.validate_plan(plan, [bundle()], ['s1'], set())

    def test_plan_detects_narration_change_and_invalid_cues(self):
        raw = {'summary': 'Shorter', 'replacements': [{'source_id': 's1', 'scene': {
            'type': 'next', 'title': 'New', 'say': 'Chào bạn.'}}]}
        plan = m.validate_plan(raw, [bundle()], ['s1'], set())
        self.assertEqual(plan.replacements[0].scene['say'], 'Chào bạn.')
        raw['replacements'][0]['scene']['sub'] = 'x' * 10000
        with self.assertRaises(ValueError):
            m.validate_plan(raw, [bundle()], ['s1'], set())

    def test_source_paths_and_extra_plan_fields_are_rejected(self):
        with self.assertRaises(ValueError):
            m.validate_plan({'summary': 'Oops', 'replacements': [{'source_id': 's1', 'shell': 'x'}]},
                            [bundle()], ['s1'], set())


class QwenTests(unittest.TestCase):
    def test_provider_error_never_exposes_key_or_response_body(self):
        import httpx
        from factory import editor_llm
        def fake_post(*args, **kwargs):
            return httpx.Response(401, json={'error': 'secret-value'}, request=httpx.Request('POST', 'https://example.com'))
        settings = {'EDITOR_LLM_BASE_URL': 'https://example.com/v1', 'EDITOR_LLM_API_KEY': 'secret-value',
                    'EDITOR_LLM_MODEL': 'qwen-test'}
        with patch.object(editor_llm, 'setting', side_effect=lambda k, d='': settings.get(k, d)), \
             patch('httpx.Client.post', side_effect=fake_post):
            with self.assertRaises(RuntimeError) as ctx:
                editor_llm.interpret('Edit', [], [], [], {})
        self.assertNotIn('secret-value', str(ctx.exception))
        self.assertIn('401', str(ctx.exception))


if __name__ == '__main__':
    unittest.main()

class StoreTests(unittest.TestCase):
    def setUp(self):
        from factory import editor
        self.editor = editor
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.patcher = patch.object(editor, 'RUNS_DIR', self.root)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        job = self.root / 'job'
        (job / 'editor/revisions/baseline').mkdir(parents=True)
        (job / 'spec.json').write_text('{"id":"test","title":"Test","scenes":[{"type":"next","title":"Hello","say":"Xin chào."}]}')
        (job / 'job.json').write_text('{"id":"job","engines":{"remotion":{"status":"done"}}}')
        self.editor.write_json(job / 'editor/state.json', {'current': 'baseline', 'requests': {}})
        self.editor.write_json(job / 'editor/revisions/baseline/revision.json',
                               {'id': 'baseline', 'status': 'ready', 'summary': 'Original'})
        self.editor.write_json(job / 'editor/revisions/baseline/bundle.json',
                               {'bundles': [bundle()], 'meta': {'title': 'Test'}, 'diagrams': {}})

    def test_path_traversal_rejected(self):
        for name in ('../escape', 'a/b', '.', ''):
            with self.assertRaises(ValueError):
                self.editor.root(name)

    def test_submit_is_idempotent_and_rejects_stale_parent(self):
        with patch.object(self.editor, '_enqueue') as enqueue:
            request = {'parent': 'baseline', 'start': 0, 'end': 3, 'prompt': 'Change heading', 'request_id': 'request-1'}
            a = self.editor.submit('job', request)
            b = self.editor.submit('job', request)
            self.assertEqual(a['id'], b['id'])
            self.assertEqual(enqueue.call_count, 1)
            request['request_id'] = 'request-2'
            request['parent'] = 'unknown'
            with self.assertRaises(ValueError):
                self.editor.submit('job', request)

    def test_accept_requires_ready_revision_and_expected_current(self):
        with self.assertRaises(ValueError):
            self.editor.accept('job', 'baseline', 'stale')
        self.assertEqual(self.editor.accept('job', 'baseline', 'baseline')['current'], 'baseline')

    def test_interrupted_work_recovers_as_failure(self):
        path = self.root / 'job/editor/revisions/baseline/revision.json'
        self.editor.write_json(path, {'id': 'baseline', 'status': 'rendering'})
        self.editor.recover_interrupted()
        self.assertEqual(self.editor.read_json(path)['status'], 'failed')

    def test_invalid_image_rejected_without_registering_asset(self):
        with self.assertRaises(ValueError):
            self.editor.upload('job', b'not an image', 'bad.svg')
        self.assertFalse(list((self.root / 'job/editor/assets').glob('*.json')))

class ApiTests(StoreTests):
    def test_editor_routes_return_timeline_and_reject_invalid_range(self):
        from fastapi import HTTPException
        from factory.app import app
        from factory import editor_api
        self.assertIn('/api/jobs/{job_id}/editor/revisions', app.openapi()['paths'])
        result = editor_api.revision('job', 'baseline')
        self.assertEqual(result['scenes'][0]['id'], 's1')
        with self.assertRaises(HTTPException) as ctx:
            editor_api.submit('job', {'parent': 'baseline', 'start': 1, 'end': 0,
                                     'prompt': 'Change', 'request_id': 'bad'})
        self.assertEqual(ctx.exception.status_code, 422)

    def test_legacy_rerun_preserves_editor_store(self):
        from factory import jobs
        with patch.object(jobs, 'RUNS_DIR', self.root):
            with self.assertRaises(ValueError):
                jobs.rerun('job', 'remotion')
        self.assertTrue((self.root / 'job/editor/state.json').exists())
