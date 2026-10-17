"""Recover editable media and render revisions with scene-local audio/timings."""

import copy
import hashlib
import json
import math
import shutil
import subprocess
import uuid
from pathlib import Path

from . import editor
from .config import CACHE_DIR
from .editor_models import FPS, assemble, shift_scene
from .spec import Spec


def command(args, **kwargs):
    try:
        return subprocess.run([str(x) for x in args], capture_output=True, check=True, timeout=180, **kwargs)
    except subprocess.SubprocessError:
        raise RuntimeError('FFmpeg không xử lý được media của cảnh; kiểm tra file nguồn.') from None


def audio_segment(source: Path, out: Path, duration: float, *, start=0.0, lead=0.0):
    out.parent.mkdir(parents=True, exist_ok=True)
    command(['ffmpeg','-v','error','-y','-ss',start,'-i',source,'-vn', '-af',
             f'adelay={round(lead*1000)}:all=1,apad,atrim=duration={duration}',
             '-ar','48000','-ac','2','-c:a','pcm_s16le',out])


def localize(data: dict, sources: list[dict]) -> list[dict]:
    if len(data['scenes']) != len(sources):
        raise ValueError('Kịch bản nguồn không khớp số cảnh đã dựng.')
    bundles=[]
    for i, (s, source) in enumerate(zip(data['scenes'], sources)):
        start,end=round(s['start']*FPS)/FPS,round(s['end']*FPS)/FPS
        indices=[n for n,w in enumerate(data['words']) if start <= w['start'] < end]
        base=indices[0] if indices else 0
        words=[dict(data['words'][n],start=data['words'][n]['start']-start,end=data['words'][n]['end']-start) for n in indices]
        phrases=[dict(p,**{'from':p['from']-base,'to':p['to']-base},start=p['start']-start,end=p['end']-start)
                 for p in data['phrases'] if p['from'] in indices and p['to'] in indices]
        beats=[dict(b,t0=max(0,b['t0']-start),t1=min(end,b['t1'])-start) for b in data.get('beats',[])
               if b.get('scene')==i or ('scene' not in b and start <= b['t0'] < end)]
        duration=end-start
        bundles.append({'id':s.get('id') or f's{i+1}', 'source':copy.deepcopy(source),
                        'scene':dict(shift_scene(s,-start),start=0,end=duration), 'words':words,'phrases':phrases,'beats':beats,
                        'duration':duration,'base_duration':duration,'hold_seconds':0,'audio':''})
    return bundles


def capture_sources(data: dict, audio: Path, stage: Path, destination: Path):
    """Ordinary renders retain recoverable sources before deleting the staging area."""
    destination.mkdir(parents=True,exist_ok=True)
    editor.write_json(destination/'data.json',data)
    images=destination/'images'
    images.mkdir(exist_ok=True)
    for beat in data.get('beats',[]):
        src=stage/Path(beat['src']).name
        if src.is_file():
            shutil.copy2(src,images/src.name)
    if audio.is_file():
        shutil.copy2(audio,destination/'narration.wav')


def _legacy_assets(job: Path, data: dict) -> dict[str,Path]:
    """Match sibling assets by recorded content/timing, never basename alone."""
    result={}
    html=job/'hyperframes/comp/index.html'
    if html.exists():
        text=html.read_text(encoding='utf-8')
        marker='window.__DATA = '
        if marker in text:
            sibling=json.JSONDecoder().raw_decode(text.split(marker,1)[1])[0]
            for beat in data.get('beats',[]):
                for other in sibling.get('beats',[]):
                    if all(beat.get(k)==other.get(k) for k in ('page','q','text','t0','t1')) and beat.get('page'):
                        rel=Path(other['src'])
                        candidate=(html.parent/rel).resolve()
                        if candidate.is_relative_to(html.parent.resolve()) and candidate.is_file():
                            result[beat['src']]=candidate
                            break
    # Recover exact provider image by its recorded source page if sibling is absent.
    pages={b.get('page'):b['src'] for b in data.get('beats',[]) if b.get('page') and b['src'] not in result}
    if pages:
        for meta in (CACHE_DIR/'stock/photos').glob('*.json'):
            try:
                page=editor.read_json(meta).get('page')
                if page in pages:
                    image=meta.with_suffix('.jpg')
                    if image.is_file():
                        result[pages[page]]=image
            except (OSError,ValueError):
                continue
    return result


def import_baseline(job_id: str):
    folder=editor.root(job_id)
    job=folder.parent
    engine=job/'remotion'
    source=engine/'sources'
    props=source/'data.json'
    data=editor.read_json(props) if props.exists() else editor.read_json(engine/'props.json')['data']
    spec=editor.read_json(job/'spec.json')
    recovered=_legacy_assets(job,data) if not props.exists() else {}
    assets=folder/'assets'
    assets.mkdir(exist_ok=True)
    missing=[]
    for beat in data.get('beats',[]):
        candidate=source/'images'/Path(beat['src']).name if props.exists() else recovered.get(beat['src'])
        if candidate and candidate.is_file():
            aid=hashlib.sha256(candidate.read_bytes()).hexdigest()[:32]
            dest=assets/(aid+candidate.suffix.lower())
            if not dest.exists():
                shutil.copy2(candidate,dest)
            beat['src']=str(dest.relative_to(folder))
        else:
            missing.append(beat.get('scene'))
            beat['src']='missing/'+Path(beat['src']).name
    bundles=localize(data,spec['scenes'])
    revision=editor.revision_dir(job_id,'baseline')
    for i,b in enumerate(bundles):
        dest=revision/'audio'/f'{b["id"]}.wav'
        # Normalize each audio slot to the frame-quantized schedule used by the editor.
        duration=math.ceil(b['duration']*FPS-1e-7)/FPS
        audio_segment(engine/'video.mp4',dest,duration,start=round(data['scenes'][i]['start']*FPS)/FPS)
        b['audio']=str(dest.relative_to(folder))
    editor.write_json(revision/'bundle.json',{'bundles':bundles,'meta':data['meta'],'diagrams':data['diagrams']})
    shutil.copy2(engine/'video.mp4',revision/'video.mp4')
    if (engine/'thumb.jpg').exists():
        shutil.copy2(engine/'thumb.jpg',revision/'thumb.jpg')
    if (engine/'credits.txt').exists():
        shutil.copy2(engine/'credits.txt',revision/'credits.txt')
    warnings=[]
    if missing:
        warnings.append('Thiếu ảnh nguồn tại cảnh '+', '.join(str(i+1) for i in sorted(set(missing)) if i is not None)+
                        '. Hãy đính kèm ảnh thay thế cho các cảnh này trước khi dựng.')
    editor.update(job_id,'baseline',warnings=warnings,duration=data['duration'])


def change_scene(bundle: dict, source: dict, spec_raw: dict, diagrams: dict, workdir: Path, log) -> tuple[dict,dict]:
    from .flow import compile_flows
    from .narration import CueFinder, _resolve_cues, attach_punctuation, build_phrases, synthesize_spec
    b=copy.deepcopy(bundle)
    changed=source['say'] != b['source']['say'] or not b.get('audio')
    if changed:
        spec=Spec.model_validate(dict(spec_raw,id=spec_raw.get('id','edit'),title=spec_raw.get('title','Edit'),scenes=[source]))
        speech,words,dur=synthesize_spec(source['say'],spec)
        words=copy.deepcopy(words)
        attach_punctuation(source['say'],words)
        local=[dict(w,start=w['start']+.15,end=w['end']+.15,scene=0) for w in words]
        b['words']=[{'display':w['display'],'start':w['start'],'end':w['end']} for w in local]
        b['phrases']=build_phrases(local)
        b['duration']=math.ceil((.15+dur+.4)*FPS)/FPS
        b['base_duration']=b['duration']
        b['hold_seconds']=0
        out=workdir/'audio'/f'{uuid.uuid4().hex}.wav'
        audio_segment(speech,out,b['duration'],lead=.15)
        b['audio']=str(out)
        # Keep existing images at proportional local positions when speech changes.
        old_duration=max(bundle['duration'],.01)
        for beat in b['beats']:
            beat['t0']=beat['t0']/old_duration*b['duration']
            beat['t1']=beat['t1']/old_duration*b['duration']
    raw=dict(spec_raw,scenes=[source],diagrams=diagrams)
    compiled=compile_flows(raw)
    scene={k:v for k,v in compiled['scenes'][0].items() if k!='say'}
    extra={}
    if source['type']=='flow':
        old=scene['diagram']
        new='edit_'+uuid.uuid4().hex[:12]
        extra[new]=compiled['diagrams'][old]
        scene['diagram']=new
    elif source['type']=='diagram' and source.get('diagram') not in diagrams:
        raise ValueError('Sơ đồ không tồn tại; hãy dùng kiểu flow để tạo sơ đồ mới.')
    cue_words=[dict(w,text=w['display']) for w in b['words']]
    cues=CueFinder(cue_words,'editor',log)
    _resolve_cues(scene,cues,.1)
    if source['type']=='tip':
        scene['answer_t']=max(.1,cues.time_of(source.get('answer_cue',''))-.3)
    scene.update(start=0,end=b['duration'],audio_at=.15 if changed else b['scene'].get('audio_at',.15))
    b.update(source=copy.deepcopy(source),scene=scene)
    return b,extra


def prepare_revision(job_id: str,rid: str,parent: dict,selected: list[str],plan):
    folder=editor.root(job_id)
    dest=editor.revision_dir(job_id,rid)
    spec=editor.read_json(folder.parent/'spec.json')
    diagrams=copy.deepcopy(parent['diagrams'])
    by_id={b['id']:b for b in parent['bundles']}
    changed=[]
    for entry in plan.replacements:
        if entry.source_id:
            b=copy.deepcopy(by_id[entry.source_id])
        else:
            b={'id':'s'+uuid.uuid4().hex[:12],'source':{'say':''},'scene':{},'duration':1,
               'base_duration':1,'hold_seconds':0,'words':[],'phrases':[],'beats':[],'audio':''}
        if entry.scene:
            b,extra=change_scene(b,entry.scene,spec,diagrams,dest,lambda _:None)
            diagrams.update(extra)
            # Persist compiled flow ID so future edits can refer to this diagram too.
        b['id']='s'+uuid.uuid4().hex[:12] if any(x['id']==b['id'] for x in changed) else b['id']
        audio=Path(b['audio'])
        if audio.is_absolute():
            b['audio']=str(audio.relative_to(folder))
        if entry.hold_seconds is not None:
            b['hold_seconds']=entry.hold_seconds
            b['duration']=b['base_duration']+entry.hold_seconds
        if entry.animation is not None:
            b['animation']=entry.animation
        if entry.image_asset_id:
            info=editor.asset(job_id,entry.image_asset_id)
            b['beats']=[{'t0':0,'t1':b['duration'],'src':str(Path(info['path']).relative_to(folder)),
                         'page':'','provider':'upload'}]
        if entry.stock_query:
            from .config import stock_provider, stock_api_key
            from .beats import _pexels
            from . import pixabay
            provider=stock_provider()
            key=stock_api_key(provider)
            if not key:
                raise ValueError('Cần key Pixabay/Pexels để thay bằng ảnh stock, hoặc đính kèm ảnh.')
            image=(pixabay.photo if provider=='pixabay' else _pexels)(entry.stock_query,set(),key)
            if image is None:
                raise ValueError('Không tìm được ảnh stock cho yêu cầu; hãy đính kèm ảnh thay thế.')
            aid=hashlib.sha256(image.read_bytes()).hexdigest()[:32]
            target=folder/'assets'/(aid+image.suffix)
            shutil.copy2(image,target)
            page=editor.read_json(image.with_suffix('.json')).get('page','') if image.with_suffix('.json').exists() else ''
            b['beats']=[{'t0':0,'t1':b['duration'],'src':str(target.relative_to(folder)),
                         'page':page,'provider':provider}]
        # New/rebuilt flows use compiled diagrams; require no external image service.
        changed.append(b)
    first=next(i for i,b in enumerate(parent['bundles']) if b['id'] in selected)
    result=copy.deepcopy(parent)
    result['diagrams']=diagrams
    result['bundles']=parent['bundles'][:first]+changed+parent['bundles'][first+len(selected):]
    editor.write_json(dest/'bundle.json',result)
    pages=list(dict.fromkeys(b.get('page') for x in result['bundles'] for b in x['beats'] if b.get('page')))
    (dest/'credits.txt').write_text('Ảnh nền:\n'+'\n'.join(pages),encoding='utf-8')


def render_revision(job_id: str,rid: str):
    from .engines.remotion import render_prepared
    folder=editor.root(job_id)
    dest=editor.revision_dir(job_id,rid)
    source=editor.read_json(dest/'bundle.json')
    data=assemble(source['bundles'],source['meta'],source['diagrams'])
    # Resolve only job-owned assets/audio. Fail explicitly if legacy sources are missing.
    for beat in data['beats']:
        path=(folder/beat['src']).resolve()
        if not path.is_relative_to(folder.resolve()) or not path.is_file():
            raise ValueError('Thiếu ảnh gốc: hãy tải ảnh thay thế cho cảnh tương ứng.')
    audio_files=[]
    for i,(b,s) in enumerate(zip(source['bundles'],data['scenes'])):
        path=(folder/b['audio']).resolve()
        if not path.is_relative_to(folder.resolve()) or not path.is_file():
            raise ValueError('Thiếu giọng đọc nguồn.')
        piece=dest/'audio-slots'/f'{i:03}.wav'
        audio_segment(path,piece,s['end']-s['start'])
        audio_files.append(piece)
    listing=dest/'audio-slots/concat.txt'
    # Relative generated filenames contain no user-controlled shell/concat syntax.
    listing.write_text(''.join(f"file '{p.name}'\n" for p in audio_files),encoding='utf-8')
    audio=dest/'narration.wav'
    command(['ffmpeg','-v','error','-y','-f','concat','-safe','0','-i',listing,'-c:a','pcm_s16le',audio])
    editor.write_json(dest/'timeline.json',data)
    render_prepared(data,audio,folder,dest,lambda message:editor.update(job_id,rid,message=message))
