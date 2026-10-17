const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const elements=new Map();
function el(id){
 if(!elements.has(id))elements.set(id,{value:'',textContent:'',innerHTML:'',disabled:false,hidden:false,
  dataset:{},currentTime:0,open:false,classList:{toggle(){}},querySelectorAll(){return[];},
  addEventListener(){},removeAttribute(){},pause(){},showModal(){this.open=true;},close(){this.open=false;}});
 return elements.get(id);
}
const baseline={id:'baseline',status:'ready',duration:3,summary:'Original',scenes:[{id:'s1',type:'next',title:'A',say:'Xin chào.',start:0,end:3}]};
const state={current:'baseline',revisions:[baseline]},revisions={baseline};
const ids=[];let next=0;
const context=vm.createContext({document:{getElementById:el},window:{dispatchEvent(){}},Event:class{},
 localStorage:{getItem(){return null;},setItem(){}},crypto:{randomUUID:()=>`req-${++next}`},
 setTimeout(){},clearTimeout(){},fetch:async(url,opts={})=>{
  let body;
  if(url.endsWith('/editor'))body=state;
  else if(url.endsWith('/revisions')&&opts.method==='POST'){
   const req=JSON.parse(opts.body);ids.push(req.request_id);
   const id=`r${ids.length}`;body={...baseline,id,summary:'Updated'};revisions[id]=body;state.revisions.push(body);
  } else if(url.endsWith('/discard')) {revisions[url.split('/').at(-2)].status='discarded';body={};}
  else if(url.endsWith('/accept')){state.current=url.split('/').at(-2);body=state;}
  else body=revisions[url.split('/').at(-1)];
  return {ok:true,json:async()=>JSON.parse(JSON.stringify(body))};
 }});
vm.runInContext(fs.readFileSync('factory/web/editor.js','utf8'),context);
(async()=>{
 await context.window.openRemotionEditor('job');
 el('editPrompt').value='Change heading';el('editPrompt').oninput();
 assert.equal(el('editSubmit').disabled,false);
 await el('editSubmit').onclick();
 assert.equal(el('editVideo').dataset.revision,'r1');
 await el('editDiscard').onclick();
 assert.equal(el('editVideo').dataset.revision,'baseline');
 await el('editSubmit').onclick();
 assert.equal(ids.length,2);
 assert.notEqual(ids[0],ids[1],'A deliberate new edit after discard must not reuse the discarded request');
 await el('editAccept').onclick();
 assert.equal(state.current,'r2');
 assert.equal(el('editPrompt').value,'');
 console.log('Editor submit, discard, resubmit and accept workflow passed');
})().catch(e=>{console.error(e);process.exitCode=1;});
