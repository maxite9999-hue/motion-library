import React from 'react';
import {AbsoluteFill,OffthreadVideo,Img,Loop,Sequence,useCurrentFrame,staticFile} from 'remotion';
import {scene} from './recipes.mjs';
import {replacements} from './replacements.mjs';
import {ReplacementTemplate} from './ReplacementComposition.jsx';
export function MotionTemplate({id,options={},assets={},mediaLibrary={}}){
 if(replacements[id])return <ReplacementTemplate id={id} options={options}/>;
 const frame=useCurrentFrame(),state=scene(id,frame,options,assets);
 const layer=m=>{const asset=mediaLibrary[m.slot]||{src:m.slot,frames:900};if(!asset.src)throw Error('Missing media slot '+m.slot);const src=/^(https?:|data:|blob:)/.test(asset.src)?asset.src:staticFile(asset.src);const style={position:'absolute',left:m.x,top:m.y,width:m.w,height:m.h,overflow:'hidden',opacity:m.opacity,zIndex:m.z,filter:m.grayscale?`grayscale(${m.grayscale})`:undefined};const fit={width:'100%',height:'100%',objectFit:'cover',transform:`scale(${m.scale})`};return <div key={m.slot+'-'+m.x+'-'+m.from} style={style}><Sequence from={m.from} layout="none">{asset.type==='image'?<Img src={src} style={fit}/>:<Loop durationInFrames={asset.frames||900}><OffthreadVideo src={src} muted style={fit}/></Loop>}</Sequence></div>};
 return <AbsoluteFill style={{background:'#000',overflow:'hidden'}}>{state.media.map(layer)}<div style={{position:'absolute',inset:0,zIndex:1}} dangerouslySetInnerHTML={{__html:state.svg}}/>{state.overlay&&<div style={{position:'absolute',inset:0,zIndex:3}} dangerouslySetInnerHTML={{__html:state.overlay}}/>}</AbsoluteFill>;
}
