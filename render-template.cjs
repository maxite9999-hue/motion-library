// Assistant-facing portable export utility.
const fs=require('fs'),path=require('path'),os=require('os'),{execFileSync}=require('child_process');
const [id,configFile,outputFile]=process.argv.slice(2);
if(!id||!configFile||!outputFile)throw Error('Usage: node render-template.cjs JJ-019 content.json output.mp4');
const deps=process.env.TEMPLATE_RUNTIME;
const dep=name=>require(deps?path.join(deps,name):name);
(async()=>{
 const {specs,validate}=await import('file://'+path.join(__dirname,'templates.mjs'));
 const s=specs[id];if(!s)throw Error('Unknown template');const options=validate(id,JSON.parse(fs.readFileSync(configFile,'utf8')));
 const temp=fs.mkdtempSync(path.join(os.tmpdir(),'motion-template-'));
 const entry=path.join(temp,'entry.jsx');
 fs.writeFileSync(entry,`import React from 'react';import {Composition,registerRoot,useCurrentFrame} from 'remotion';import {renderSVG} from ${JSON.stringify(path.join(__dirname,'templates.mjs'))};const C=({options,gold})=><div dangerouslySetInnerHTML={{__html:renderSVG(${JSON.stringify(id)},useCurrentFrame(),options,{gold})}}/>;registerRoot(()=><Composition id="Template" component={C} width={1280} height={720} fps={30} durationInFrames={${s.frames}}/>);`);
 const {bundle}=dep('@remotion/bundler'),{renderMedia,selectComposition}=dep('@remotion/renderer');
 const serveUrl=await bundle({entryPoint:entry,webpackOverride:c=>({...c,resolve:{...c.resolve,modules:[...(deps?[deps]:[]),path.join(__dirname,'node_modules'),'node_modules']}})});
 const inputProps={options,gold:'data:image/jpeg;base64,'+fs.readFileSync(path.join(__dirname,'gold-plate.jpg')).toString('base64')};
 const browserExecutable=process.env.TEMPLATE_BROWSER||undefined;
 const composition=await selectComposition({serveUrl,id:'Template',inputProps,browserExecutable});
 const silent=path.join(temp,'silent.mp4');
 await renderMedia({serveUrl,composition,inputProps,browserExecutable,codec:'h264',crf:18,concurrency:2,outputLocation:silent});
 execFileSync('ffmpeg',['-v','error','-i',silent,'-i',path.join(__dirname,id+'-template.m4a'),'-map','0:v','-map','1:a','-c','copy','-movflags','+faststart','-y',path.resolve(outputFile)]);
 console.log(path.resolve(outputFile));
})();
