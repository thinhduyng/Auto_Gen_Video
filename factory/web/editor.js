/* Whole-scene editor: Qwen interprets requests; Remotion renders immutable revisions. */
const EditorTools = (() => {
  const active = new Set(['queued', 'importing', 'interpreting', 'preparing', 'rendering']);
  function parseTime(value) {
    const text = String(value).trim();
    if (!/^\d+(?:\.\d+)?$/.test(text) && !/^\d+(?::\d{1,2}){1,2}(?:\.\d+)?$/.test(text)) throw new Error('Mốc thời gian không hợp lệ.');
    const parts = text.split(':').map(Number);
    if (parts.slice(1).some(x => x >= 60)) throw new Error('Giây/phút phải nhỏ hơn 60.');
    const seconds = parts.reduce((n, x) => n * 60 + x, 0);
    if (!Number.isFinite(seconds)) throw new Error('Mốc thời gian không hợp lệ.');
    return seconds;
  }
  function formatTime(seconds) {
    const centis = Math.round(Math.max(0, seconds) * 100);
    return `${String(Math.floor(centis / 6000)).padStart(2, '0')}:${((centis % 6000) / 100).toFixed(2).padStart(5, '0')}`;
  }
  const selectedScenes = (scenes, start, end) => scenes.filter(s => s.start < end - 1e-6 && s.end > start + 1e-6);
  const canEdit = (revision, state) => revision?.status === 'ready' && revision.id === state.current && !state.revisions.some(r => active.has(r.status));
  return { parseTime, formatTime, selectedScenes, canEdit, active };
})();
if (typeof module !== 'undefined') module.exports = EditorTools;

if (typeof window !== 'undefined') (() => {
  const T = EditorTools;
  const el = id => document.getElementById(id);
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const statuses = { queued:'Đang chờ', importing:'Khôi phục nguồn', interpreting:'Qwen đang xử lý', preparing:'Chuẩn bị cảnh và giọng', rendering:'Đang dựng video', ready:'Sẵn sàng', failed:'Có lỗi', discarded:'Đã bỏ' };
  let session = null, poll = null, generation = 0;
  async function request(path, options = {}) {
    const response = await fetch(path, { headers:{'Content-Type':'application/json'}, ...options });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : `HTTP ${response.status}`);
    return body;
  }
  function notice(message, error = false) {
    el('editNotice').textContent = message;
    el('editNotice').className = 'msg' + (error ? ' err' : '');
  }
  function remember() { try { localStorage.setItem(`vf-editor-${session.job}`, session.view); } catch (_) {} }
  function stored(job) { try { return localStorage.getItem(`vf-editor-${job}`); } catch (_) { return null; } }
  function videoUrl(rid) { return `/runs/${encodeURIComponent(session.job)}/editor/revisions/${encodeURIComponent(rid)}/video.mp4`; }
  function chosen() {
    const start = T.parseTime(el('editStart').value), end = T.parseTime(el('editEnd').value);
    if (!(start < end) || end > (session.detail.duration || 0) + 1e-6) throw new Error('Chọn khoảng nằm trong video, với điểm kết thúc sau điểm bắt đầu.');
    return { start, end, scenes:T.selectedScenes(session.detail.scenes || [], start, end) };
  }
  function highlight() {
    try {
      const {scenes} = chosen();
      el('editRangeNote').textContent = scenes.length ? `Sẽ thay toàn bộ ${scenes.length} cảnh: ${T.formatTime(scenes[0].start)} → ${T.formatTime(scenes.at(-1).end)}. Độ dài có thể thay đổi.` : 'Chọn một cảnh hoặc đánh dấu khoảng trên video.';
      el('editScenes').querySelectorAll('button').forEach(b => b.classList.toggle('chosen', scenes.some(s => s.id === b.dataset.scene)));
      el('editSubmit').disabled = !T.canEdit(session.detail, session.state) || session.busy || session.uploading || !el('editPrompt').value.trim() || !scenes.length;
    } catch (e) {
      el('editRangeNote').textContent = e.message;
      el('editSubmit').disabled = true;
    }
  }
  function paint() {
    const s = session, d = s.detail, st = s.state;
    el('editStatus').textContent = statuses[d.status] || d.status;
    el('editSummary').textContent = d.summary || '';
    el('editProgress').textContent = d.message || '';
    el('editWarnings').textContent = (d.warnings || []).join('\n');
    el('editDuration').textContent = d.duration ? `${T.formatTime(d.duration)} · 30 fps` : '';
    el('editVersions').innerHTML = st.revisions.filter(r => r.status !== 'discarded').map((r,i) =>
      `<option value="${escape(r.id)}" ${r.id === s.view ? 'selected' : ''}>${r.id === 'baseline' ? 'Video gốc' : `Bản ${i}`} ${r.id === st.current ? '· đang dùng' : ''} · ${escape(statuses[r.status] || r.status)}</option>`).join('');
    el('editScenes').innerHTML = (d.scenes || []).map((scene,i) => `<button type="button" data-scene="${escape(scene.id)}"><span>${String(i+1).padStart(2,'0')} · ${T.formatTime(scene.start)}–${T.formatTime(scene.end)}</span><strong>${escape(scene.heading || scene.title || scene.question || (scene.headline || []).map(x=>x[0]).join(' ') || scene.type)}</strong><small>${escape(scene.say)}</small></button>`).join('');
    el('editScenes').querySelectorAll('button').forEach(b => b.onclick = () => {
      const scene = d.scenes.find(x=>x.id === b.dataset.scene);
      el('editStart').value = scene.start.toFixed(6); el('editEnd').value = scene.end.toFixed(6);
      s.rangeTouched = true; el('editVideo').currentTime = scene.start; highlight();
    });
    if (!s.rangeTouched && d.scenes?.length) {
      el('editStart').value = d.scenes[0].start.toFixed(6); el('editEnd').value = d.scenes[0].end.toFixed(6);
    }
    const player = el('editVideo');
    if (d.status === 'ready' && player.dataset.revision !== s.view) {
      player.src = videoUrl(s.view); player.dataset.revision = s.view;
    }
    const running = st.revisions.some(r => T.active.has(r.status));
    el('editAccept').disabled = d.status !== 'ready' || d.id === st.current || s.busy || running;
    el('editAccept').textContent = d.id === st.current ? 'Đang dùng phiên bản này' : 'Dùng phiên bản này';
    el('editPublish').disabled = d.status !== 'ready' || s.busy;
    el('editDiscard').disabled = d.id === 'baseline' || d.id === st.current || T.active.has(d.status) || s.busy;
    el('editRetry').hidden = d.status !== 'failed'; el('editRetry').disabled = s.busy || running;
    el('editPrompt').disabled = !T.canEdit(d,st) || s.busy;
    el('editImageFiles').disabled = !T.canEdit(d,st) || s.busy || s.uploading || s.images.length >= 4;
    el('editCurrentNote').textContent = d.status === 'ready' && d.id !== st.current ? 'Đây là bản xem thử. Chọn “Dùng phiên bản này” để tiếp tục chỉnh sửa từ bản này.' : '';
    el('editDownload').hidden = d.status !== 'ready'; el('editDownload').href = videoUrl(s.view);
    highlight();
  }
  async function refresh(token = generation) {
    clearTimeout(poll);
    const s = session;
    const state = await request(s.base);
    if (!session || token !== generation) return;
    s.state = state;
    if (!s.view || !state.revisions.some(r => r.id === s.view && r.status !== 'discarded')) {
      const saved = stored(s.job);
      s.view = state.revisions.find(r => T.active.has(r.status))?.id || (state.revisions.some(r=>r.id===saved && r.status!=='discarded') ? saved : state.current);
    }
    const view = s.view;
    const detail = await request(`${s.base}/revisions/${view}`);
    if (!session || token !== generation || view !== s.view) return;
    s.detail = detail; remember(); paint();
    if (state.revisions.some(r => T.active.has(r.status))) poll = setTimeout(()=>refresh(token).catch(e=>notice(e.message,true)), 2000);
  }
  async function action(fn) {
    const token = generation, s = session;
    if (s.busy) return;
    s.busy = true; paint(); notice('');
    try { await fn(s); if (token === generation) await refresh(token); }
    catch (e) { if (token === generation) notice(e.message,true); }
    finally { if (token === generation) { s.busy = false; paint(); } }
  }
  function paintImages() {
    el('editImages').innerHTML = session.images.map(img=>`<div><img alt="${escape(img.name)}" src="/runs/${encodeURIComponent(session.job)}/editor/assets/${img.id}.jpg"><span>${escape(img.name)}</span><button type="button" data-remove="${img.id}" aria-label="Bỏ ảnh">×</button></div>`).join('');
    el('editImages').querySelectorAll('button').forEach(b=>b.onclick=()=>{session.images=session.images.filter(x=>x.id!==b.dataset.remove); paintImages();paint();});
  }
  window.openRemotionEditor = async job => {
    clearTimeout(poll); const token = ++generation;
    session = {job,base:`/api/jobs/${encodeURIComponent(job)}/editor`,state:{current:'baseline',revisions:[]},detail:{status:'queued'},images:[],busy:false,uploading:false,view:null,rangeTouched:false};
    const dialog = el('editorDialog');
    el('editVideo').removeAttribute('src'); delete el('editVideo').dataset.revision;
    el('editPrompt').value=''; el('editStart').value='00:00'; el('editEnd').value='00:01';
    notice('Đang mở nguồn chỉnh sửa…'); paintImages(); paint();
    if (!dialog.open) dialog.showModal();
    try { await request(session.base,{method:'POST'}); if (token===generation) { await refresh(token); notice(''); } }
    catch(e) { if(token===generation) notice(e.message,true); }
  };
  const dialog = el('editorDialog');
  el('editClose').onclick = ()=>dialog.close();
  dialog.addEventListener('close',()=>{++generation;clearTimeout(poll);el('editVideo').pause();session=null;});
  el('editStart').oninput = el('editEnd').oninput = ()=>{session.rangeTouched=true;highlight();};
  el('editMarkStart').onclick = ()=>{el('editStart').value=el('editVideo').currentTime.toFixed(6);session.rangeTouched=true;highlight();};
  el('editMarkEnd').onclick = ()=>{el('editEnd').value=el('editVideo').currentTime.toFixed(6);session.rangeTouched=true;highlight();};
  el('editPrompt').oninput = highlight;
  el('editVersions').onchange = async event => {session.view=event.target.value;session.rangeTouched=false;await refresh().catch(e=>notice(e.message,true));};
  el('editSubmit').onclick = ()=>action(async s=>{
    const range=chosen();
    const payload={parent:s.state.current,start:range.start,end:range.end,prompt:el('editPrompt').value.trim(),assets:s.images.map(x=>x.id)};
    const fingerprint=JSON.stringify(payload);
    if(s.lastFingerprint!==fingerprint){s.requestId=crypto.randomUUID();s.lastFingerprint=fingerprint;}
    payload.request_id=s.requestId;
    const result=await request(`${s.base}/revisions`,{method:'POST',body:JSON.stringify(payload)});
    s.requestId=null;s.lastFingerprint=null;
    if(session!==s)return;
    s.view=result.id;s.rangeTouched=false;remember();
  });
  el('editAccept').onclick = ()=>action(async s=>{
    await request(`${s.base}/revisions/${s.view}/accept`,{method:'POST',body:JSON.stringify({expected_current:s.state.current})});
    if(session!==s)return;
    el('editPrompt').value='';s.images=[];paintImages();s.rangeTouched=false;
  });
  el('editRetry').onclick = ()=>action(s=>request(`${s.base}/revisions/${s.view}/retry`,{method:'POST'}));
  el('editDiscard').onclick = ()=>action(async s=>{
    await request(`${s.base}/revisions/${s.view}/discard`,{method:'POST'});if(session!==s)return;s.view=s.state.current;s.rangeTouched=false;
  });
  el('editPublish').onclick = ()=>action(async s=>{
    await request(`${s.base}/revisions/${s.view}/publish`,{method:'POST'});
    if(session!==s)return;
    notice('Đã chọn phiên bản này để đăng.');window.dispatchEvent(new Event('editorPublished'));
  });
  el('editImageFiles').onchange = async event => {
    const s=session,token=generation,files=[...event.target.files];event.target.value='';
    s.uploading=true;paint();
    try {
      for(const file of files){
        if(s.images.length>=4)throw new Error('Mỗi yêu cầu nhận tối đa 4 ảnh.');
        if(file.size>8*1024*1024)throw new Error('Ảnh vượt quá 8 MB.');
        const img=await request(`${s.base}/images?name=${encodeURIComponent(file.name)}`,{method:'POST',headers:{'Content-Type':'application/octet-stream'},body:file});
        if(token!==generation)return;
        s.images.push(img);paintImages();
      }
    }catch(e){if(token===generation)notice(e.message,true);}
    finally{if(token===generation){s.uploading=false;paint();}}
  };
})();
