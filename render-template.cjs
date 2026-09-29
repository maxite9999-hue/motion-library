// Assistant-facing export utility. User only supplies ID, copy and recording.
const fs=require('fs'),path=require('path'),{execFileSync}=require('child_process');
const root=__dirname;
const dependencyRoot=process.env.REMOTION_NODE_MODULES;
function dep(name){return require(dependencyRoot?path.join(dependencyRoot,name):name)}
async function main(){
 const [id,configPath,destination]=process.argv.slice(2);if(!id||!configPath||!destination)throw Error('Usage: node render-template.cjs JJ-002 config.json output.mp4');
 const {specs,validate}=await import('file://'+root+'/recipes.mjs');const config=JSON.parse(fs.readFileSync(configPath,'utf8'));const options=validate(id,config.options||config);
 const {bundle}=dep('@remotion/bundler'),{renderMedia,selectComposition}=dep('@remotion/renderer');
 const media=JSON.parse(fs.readFileSync(root+'/media.json','utf8'));const mediaLibrary={...Object.fromEntries(Object.entries(media).map(([k,m])=>[k,{src:m.file,frames:m.frames}])),...config.mediaLibrary};
 const serveUrl=await bundle({entryPoint:root+'/entry.jsx',publicDir:root,webpackOverride:c=>({...c,resolve:{...c.resolve,modules:dependencyRoot?[dependencyRoot,'node_modules']:['node_modules']}})});
 const inputProps={id,options,mediaLibrary,assets:{gold:'data:image/jpeg;base64,'+fs.readFileSync(root+'/gold-plate.jpg').toString('base64')}};
 const browserExecutable=process.env.REMOTION_BROWSER_EXECUTABLE||undefined;
 const composition=await selectComposition({serveUrl,id,inputProps,browserExecutable});
 const tmp=fs.mkdtempSync(path.join(require('os').tmpdir(),'motion-export-')),silent=tmp+'/silent.mp4';
 await renderMedia({serveUrl,composition,inputProps,browserExecutable,codec:'h264',crf:20,concurrency:2,outputLocation:silent});
 const audio=config.audio||root+'/'+id+'-template.m4a';
 execFileSync('ffmpeg',['-v','error','-i',silent,'-i',audio,'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-af','apad','-t',String(specs[id].frames/30),'-movflags','+faststart','-y',path.resolve(destination)],{stdio:'inherit'});
 console.log(path.resolve(destination));
}
main().catch(e=>{console.error(e.message);process.exitCode=1});
