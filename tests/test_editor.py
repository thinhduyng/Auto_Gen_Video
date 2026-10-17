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

class StoreFixture(unittest.TestCase):
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


class StoreTests(StoreFixture):
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

class ApiTests(StoreFixture):
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

class MediaTests(unittest.TestCase):
    def test_localization_and_reassembly_keep_caption_indices_and_diagram_cues(self):
        from factory.editor_media import localize
        data = {'meta': {'title':'Test'}, 'duration': 5, 'diagrams': {},
                'scenes': [{'type':'next','title':'A','start':0,'end':3,'audio_at':.15},
                           {'type':'diagram','heading':'B','diagram':'d','start':3,'end':5,'audio_at':3.15,
                            'events':[{'t':3.5}]}],
                'words':[{'display':'A','start':.15,'end':1}, {'display':'B','start':3.15,'end':4}],
                'phrases':[{'from':0,'to':0,'start':.15,'end':1}, {'from':1,'to':1,'start':3.15,'end':4}],
                'beats':[]}
        sources=[{'type':'next','title':'A','say':'A.'}, {'type':'diagram','heading':'B','diagram':'d','say':'B.'}]
        local=localize(data,sources)
        self.assertEqual(local[1]['scene']['events'][0]['t'], .5)
        self.assertEqual(local[1]['phrases'][0]['from'], 0)
        local[0]['duration']=4
        out=m.assemble(local, data['meta'], {})
        self.assertEqual(out['phrases'][1]['from'], 1)
        self.assertEqual(out['phrases'][1]['start'], 4.15)

    def test_visual_edit_reuses_audio_and_updates_scene_text(self):
        from factory.editor_media import change_scene
        b=bundle()
        b['base_duration']=3
        source=dict(b['source'],title='New')
        with patch('factory.narration.synthesize_spec', side_effect=AssertionError('must not synthesize')):
            result, diagrams = change_scene(b, source, {}, {}, Path('/tmp'), lambda x: None)
        self.assertEqual(result['audio'], b['audio'])
        self.assertEqual(result['scene']['title'], 'New')
        self.assertEqual(result['words'], b['words'])

    def test_rewrite_changes_speech_and_duration_without_mutating_source(self):
        from factory.editor_media import change_scene
        with tempfile.TemporaryDirectory() as folder:
            b=bundle()
            source=dict(b['source'],say='Một lời đọc mới dài hơn.')
            words=[{'text':'Một','start':0,'end':.4}, {'text':'hơn','start':5.5,'end':6}]
            with patch('factory.narration.synthesize_spec', return_value=(Path('/tmp/fake.mp3'),words,6)), \
                 patch('factory.editor_media.audio_segment'):
                result, _ = change_scene(b,source,{}, {},Path(folder),lambda x:None)
            self.assertGreater(result['duration'],6)
            self.assertEqual(result['source']['say'],source['say'])
            self.assertEqual(b['source']['say'],'Xin chào.')

class ValidationTests(unittest.TestCase):
    def test_malformed_renderer_shapes_are_rejected(self):
        for scene in [
            {'type':'title','say':'Xin chào.','headline':'not a list'},
            {'type':'bullets','say':'Xin chào.','heading':'A','items':['bad']},
            {'type':'compare','say':'Xin chào.','heading':'A','left':{'title':'A','points':[{}]},'right':{'title':'B','points':[]}},
            {'type':'next','say':'Xin chào.','title':{'bad':'object'}},
        ]:
            with self.assertRaises(ValueError):
                m.validate_plan({'summary':'Edit','replacements':[{'source_id':'s1','scene':scene}]},[bundle()],['s1'],set())

    def test_conflicting_image_sources_are_rejected(self):
        with self.assertRaises(ValueError):
            m.validate_plan({'summary':'Edit','replacements':[{'source_id':'s1','image_asset_id':'x','stock_query':'paper'}]},
                            [bundle()],['s1'],{'x'})

    def test_stock_query_is_a_supported_edit(self):
        plan=m.validate_plan({'summary':'Image','replacements':[{'source_id':'s1','stock_query':'paper origami'}]},
                             [bundle()],['s1'],set())
        self.assertEqual(plan.replacements[0].stock_query,'paper origami')

class RevisionPipelineTests(StoreFixture):
    def test_render_retry_reuses_plan_and_keeps_original(self):
        from factory import editor_llm, editor_media
        request={'parent':'baseline','start':0,'end':3,'prompt':'Change title','request_id':'pipeline'}
        with patch.object(self.editor,'_enqueue'):
            info=self.editor.submit('job',request)
        plan={'summary':'Updated title','replacements':[{'source_id':'s1','scene':{
              'type':'next','title':'Origami mới','say':'Xin chào.'}}]}
        with patch.object(editor_llm,'interpret',return_value=plan) as llm, \
             patch.object(editor_media,'render_revision',side_effect=[RuntimeError('render failed'),None]):
            self.editor._process('job',info['id'])
            self.assertEqual(self.editor.revision('job',info['id'])['status'],'failed')
            self.editor._process('job',info['id'])
            self.assertEqual(self.editor.revision('job',info['id'])['status'],'ready')
            self.assertEqual(llm.call_count,1)
        new=self.editor.read_json(self.editor.revision_dir('job',info['id'])/'bundle.json')
        self.assertEqual(new['bundles'][0]['source']['title'],'Origami mới')
        old=self.editor.read_json(self.editor.revision_dir('job','baseline')/'bundle.json')
        self.assertEqual(old['bundles'][0]['source']['title'],'Hello')
        self.assertEqual(self.editor.state('job')['current'],'baseline')

    def test_valid_image_upload_is_normalized_and_referenced_by_id(self):
        import subprocess
        image=subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=blue:s=64x64',
                              '-frames:v','1','-f','image2pipe','-vcodec','png','pipe:1'],
                             capture_output=True,check=True).stdout
        info=self.editor.upload('job',image,'../../image.png')
        saved=self.editor.asset('job',info['id'])
        self.assertEqual(saved['name'],'image.png')
        self.assertTrue(Path(saved['path']).is_file())
        self.assertEqual(Path(saved['path']).parent,self.root/'job/editor/assets')

    def test_idempotency_key_cannot_be_reused_for_different_request(self):
        with patch.object(self.editor,'_enqueue'):
            req={'parent':'baseline','start':0,'end':3,'prompt':'Change title','request_id':'same'}
            self.editor.submit('job',req)
            req['prompt']='Different request'
            with self.assertRaises(ValueError):
                self.editor.submit('job',req)

class DiagramValidationTests(unittest.TestCase):
    def test_origami_flow_direction_survives_validation(self):
        scene={'type':'flow','heading':'Flow','say':'Bước một. Bước hai.','direction':'right',
               'nodes':[{'id':'a','label':'A'},{'id':'b','label':'B'}],
               'edges':[{'from':'a','to':'b','style':'flow'}],
               'steps':[{'cue':'Bước một','show':['a']},{'cue':'Bước hai','show':['b']}]}
        plan=m.validate_plan({'summary':'Flow','replacements':[{'source_id':'s1','scene':scene}]},[bundle()],['s1'],set())
        self.assertEqual(plan.replacements[0].scene['direction'],'right')

    def test_invalid_cue_types_and_diagram_events_raise_value_error(self):
        scenes=[{'type':'next','title':'A','say':'Xin chào.','chips':[{'text':'A','cue':123}]},
                {'type':'diagram','heading':'A','say':'Xin chào.','diagram':'d','events':{'show':['a']}},
                {'type':'diagram','heading':'A','say':'Xin chào.','diagram':'d','events':[{'show':['missing']}]}]
        for scene in scenes:
            with self.assertRaises(ValueError):
                m.validate_plan({'summary':'Edit','replacements':[{'source_id':'s1','scene':scene}]},
                                [bundle()],['s1'],set(),{'d':{'elements':[{'id':'a'}]}})

class ConcurrencyTests(StoreFixture):
    def test_bootstrap_and_rerun_cannot_both_claim_completed_source(self):
        import shutil, threading
        from factory import jobs
        shutil.rmtree(self.root/'job/editor')
        entering,release=threading.Event(),threading.Event()
        original=self.editor.write_json
        failures=[]
        def write(path,value):
            if path.name=='state.json':
                entering.set()
                release.wait(2)
            return original(path,value)
        def rerun():
            try: jobs.rerun('job','remotion')
            except ValueError: failures.append('protected')
        with patch.object(jobs,'RUNS_DIR',self.root), patch.object(self.editor,'write_json',side_effect=write), \
             patch.object(self.editor,'_enqueue'),patch.object(jobs._pool,'submit') as render:
            a=threading.Thread(target=lambda:self.editor.bootstrap('job'))
            a.start();self.assertTrue(entering.wait(2))
            b=threading.Thread(target=rerun);b.start()
            b.join(.03)
            release.set();a.join(2);b.join(2)
            self.assertEqual(render.call_count,0)
            self.assertEqual(failures,['protected'])

class LegacyCueTests(unittest.TestCase):
    def test_case_only_legacy_cue_is_canonicalized_to_narration(self):
        scene={'type':'bullets','heading':'Robot','say':'robot nuốt được từ ruột sấy khô.',
               'items':[{'text':'Robot','cue':'Robot nuốt được từ ruột sấy khô'}]}
        plan=m.validate_plan({'summary':'Keep','replacements':[{'source_id':'s1','scene':scene}]},[bundle()],['s1'],set())
        self.assertEqual(plan.replacements[0].scene['items'][0]['cue'],'robot nuốt được từ ruột sấy khô')

    def test_title_size_uses_bounded_number(self):
        scene={'type':'title','say':'Xin chào.','headline':[['Chào',True]],'size':140}
        plan=m.validate_plan({'summary':'Title','replacements':[{'source_id':'s1','scene':scene}]},[bundle()],['s1'],set())
        self.assertEqual(plan.replacements[0].scene['size'],140)

class HTTPTests(StoreFixture):
    def test_asgi_routes_serialize_timeline_and_submit_revision(self):
        import asyncio, httpx
        from factory.app import app
        async def check():
            # Keep the loop responsive even on hosts denying asyncio wakeup socket writes.
            async def tick():
                while True:
                    await asyncio.sleep(.01)
            ticker=asyncio.create_task(tick())
            try:
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
                    result=await client.get('/api/jobs/job/editor/revisions/baseline')
                    self.assertEqual(result.status_code,200)
                    self.assertEqual(result.json()['scenes'][0]['id'],'s1')
                    result=await client.post('/api/jobs/job/editor/revisions',json={
                        'parent':'baseline','start':0,'end':3,'prompt':'Change title','request_id':'http'})
                    self.assertEqual(result.status_code,202)
                    self.assertEqual(result.json()['status'],'queued')
                    result=await client.post('/api/jobs/job/editor/revisions',json={'prompt':'bad'})
                    self.assertEqual(result.status_code,422)
            finally:
                ticker.cancel()
        with patch.object(self.editor,'_enqueue'):
            asyncio.run(check())

class MissingFieldTests(unittest.TestCase):
    def test_missing_scene_type_is_a_repairable_validation_error(self):
        with self.assertRaises(ValueError):
            m.validate_plan({'summary':'Edit','replacements':[{'source_id':'s1','scene':{'say':'Xin chào.','title':'A'}}]},
                            [bundle()],['s1'],set())

class AtomicStoreTests(StoreFixture):
    def test_failed_baseline_creation_does_not_leave_dangling_current_pointer(self):
        import shutil
        shutil.rmtree(self.root/'job/editor')
        original=self.editor.write_json
        def fail_revision(path,value):
            if path.name=='revision.json':
                raise OSError('disk failure')
            original(path,value)
        with patch.object(self.editor,'write_json',side_effect=fail_revision), patch.object(self.editor,'_enqueue'):
            with self.assertRaises(OSError):self.editor.bootstrap('job')
        self.assertFalse((self.root/'job/editor/state.json').exists())


if __name__ == '__main__':
    unittest.main()
