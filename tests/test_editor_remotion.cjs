const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve('engines/remotion-academic');
const ts = require(path.join(root,'node_modules/typescript'));
const React = require(path.join(root,'node_modules/react'));
let frame = 90, registeredRoot;
const cache = {};
function load(name) {
  if(cache[name])return cache[name];
  const code = ts.transpileModule(fs.readFileSync(path.join(root,'src',name+'.tsx'),'utf8'), {
    compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.React,esModuleInterop:true}
  }).outputText;
  const module={exports:{}};
  const requireStub = id => {
    if(id==='react')return React;
    if(id==='./lib')return load('lib');
    if(id==='./Academic')return load('Academic');
    if(id==='@remotion/fonts')return {loadFont(){}};
    if(id==='remotion')return {Composition:'composition',registerRoot:fn=>{registeredRoot=fn;},AbsoluteFill:'fill',Audio:'audio',Img:'image',staticFile:x=>x,useCurrentFrame:()=>frame,useVideoConfig:()=>({fps:30})};
    if(id==='./Diagram')return {DiagramLayer:'diagram',sceneAlpha:(t,a,b)=>t>=a&&t<b?1:0};
    if(id==='./Scenes')return new Proxy({}, {get:(_,k)=>k});
    throw new Error(id);
  };
  vm.runInNewContext(code,{module,exports:module.exports,require:requireStub});
  cache[name]=module.exports;
  return module.exports;
}
const {Academic}=load('Academic');
const data={meta:{title:'Test'},duration:6,scenes:[
 {type:'diagram',diagram:'d',start:0,end:3},
 {type:'diagram',diagram:'d',start:3,end:6}
],diagrams:{d:{w:100,h:100,elements:[]}},words:[],phrases:[],beats:[]};
// A shared diagram must not disappear when its next explanatory scene starts.
let tree=Academic({data,audio:''});
let group=tree.props.children[4][0];
assert.notEqual(group.props.style.opacity,0,'Default shared diagram must remain visible across scene boundary');
data.scenes[1].animation='fade';
tree=Academic({data,audio:''});
group=tree.props.children[4][0];
assert.equal(group.props.style.opacity,0,'Explicit fade is allowed to animate the selected diagram scene');
const {sceneEntrance}=load('lib');
assert.match(sceneEntrance(3.25,{start:3,end:6,animation:'zoom'}).transform,/scale/);
console.log('Remotion scene animation regression tests passed');

load('index');
assert.equal(registeredRoot().props.calculateMetadata({props:{data:{duration:8.3}}}).durationInFrames,249,'Frame-quantized durations must not gain an empty frame');
