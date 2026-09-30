import React from 'react';
import {AbsoluteFill,OffthreadVideo,Img,Sequence,useCurrentFrame,staticFile} from 'remotion';
import {replacements,validateReplacement} from './replacements.mjs';
const clamp=x=>Math.max(0,Math.min(1,x)),smooth=x=>{x=clamp(x);return x*x*(3-2*x)},mix=(a,b,x)=>a+(b-a)*x;
const url=s=>/^(https?:|data:|blob:)/.test(s)?s:staticFile(s),fit={width:'100%',height:'100%',objectFit:'cover'};
function Plate({src,from,to,rate=1,startFrom=0,opacity=1}){return <Sequence from={from} durationInFrames={to-from} layout="none"><div style={{position:'absolute',inset:0,opacity}}><OffthreadVideo src={url(src)} startFrom={startFrom} playbackRate={rate} muted style={fit}/></div></Sequence>}
const label=(value,x,y,size,extra={})=><text x={x} y={y} fill="white" fontSize={size} fontFamily="Arial Narrow,Arial,PingFang SC,sans-serif" textAnchor="middle" {...extra}>{value}</text>;
const Pointer=({x,y,pressed=false})=><g transform={`translate(${x} ${y}) scale(${pressed?.9:1})`}><path d="M0 0c-4-3-8 0-8 4v21L-14 19c-8-4-11 3-6 9L-4 47c5 6 24 4 27-4l7-22c1-7-4-11-8-6-2-9-9-9-12-4-1-8-9-9-12-4V4Q-1 1 0 0Z" fill="white" stroke="#444" strokeWidth="2.8"/></g>;
function Subscribe({f,p}){
 const appear=smooth((f-1069)/11),done=f>=1104,move=smooth((f-1249)/11),shrink=smooth((f-1268)/12),iconX=mix(471,813,move),iconScale=(done?smooth((f-1101)/9):0)*(1-shrink),hand=f>=1088&&f<1163;
 const handX=f<1125?mix(677,663,smooth((f-1088)/9)):mix(663,814,smooth((f-1125)/12));
 return <g opacity={f>=1281?0:1}>
 {!done&&<g transform={`translate(640 ${mix(751,600,appear)}) scale(${appear})`}><rect x="-110" y="-32" width="220" height="64" rx="8" fill="#ed0707"/>{label(p.button,0,10,28,{fontWeight:700})}</g>}
 {done&&<><g transform={`translate(${iconX} 600) rotate(${mix(-40,0,smooth((f-1104)/10))+mix(0,90,move)}) scale(${iconScale})`}><circle r="48" fill="#f10e13" stroke="white" strokeWidth="5"/><rect x="-28" y="-21" width="56" height="42" rx="9" fill="white"/><path d="M-5-12L15 0L-5 12Z" fill="#f10e13"/></g><g opacity={1-smooth((f-1248)/5)}><rect x="532" y="568" width="219" height="64" rx="5" fill="#f2f2f2"/>{label(p.done,641,611,27,{fill:'#626262',fontWeight:700})}<g opacity={smooth((f-1134)/5)} transform={`translate(814 600) rotate(${f>=1141&&f<1165?Math.sin((f-1141)*1.1)*18*(1-(f-1141)/24):0})`}><circle r="32" fill="#ddd"/><path d="M-14 8V-6Q-14-23 0-23Q14-23 14-6V8L20 15H-20Z" fill="#777"/><circle cy="21" r="5" fill="#777"/>{f>=1141&&<path d="M-25-17Q-38-2-27 12M25-17Q38-2 27 12" fill="none" stroke="#777" strokeWidth="3"/>}</g></g></>}
 {hand&&<Pointer x={handX} y={mix(743,608,smooth((f-1088)/10))} pressed={(f>=1096&&f<1101)||(f>=1141&&f<1145)}/>}
 </g>;
}
function CRT({f}){let zoom=1+smooth((f-202)/14)*.7;const band=mix(7,510,clamp((f-157)/47));return <><div style={{position:'absolute',inset:0,background:'repeating-linear-gradient(0deg,transparent 0px,transparent 1px,rgba(0,0,0,.38) 2px,rgba(255,255,255,.2) 3px)',borderRadius:Math.max(0,95-(zoom-1)*150),boxShadow:'inset 0 0 45px 25px black'}}/><svg viewBox="0 0 1280 720" style={{position:'absolute',inset:0}}><defs><filter id="glow"><feGaussianBlur stdDeviation="24"/></filter></defs><rect x="0" y={((f-117)*9)%700} width="1280" height="110" fill="white" opacity=".23" filter="url(#glow)"/>{f>=157&&f<204&&<path d={`M0 ${band}Q640 ${band-37} 1280 ${band}L1280 ${band+32}Q640 ${band-5} 0 ${band+32}Z`} fill="black"/>}</svg></>}
export function ReplacementTemplate({id,options={}}){
 const f=useCurrentFrame(),s=replacements[id],p=validateReplacement(id,options),sh=s.shots.find(x=>f>=x.from&&f<x.to),override=p.shots?.[sh?.key];
 const native=p.native===true,title005=id==='JJ-005'&&f<66&&!native,subscribe=id==='JJ-006'&&f>=1066&&f<1282&&!native,title006=id==='JJ-006'&&f>=1491&&f<2295&&!native;
 const baseVisible=!override&&!title005&&!subscribe&&!title006,gl=override&&id==='JJ-006'&&f>=852&&f<1072&&(f-sh.from<6);
 return <AbsoluteFill style={{background:'#000',overflow:'hidden'}}>
 {baseVisible&&<OffthreadVideo src={url(id+'-reference.mp4')} muted style={fit}/>}
 {override&&<Sequence from={sh.from} durationInFrames={sh.to-sh.from} layout="none"><div style={{position:'absolute',inset:0,overflow:'hidden',transform:`scale(${id==='JJ-005'&&f>=202&&f<218?1+smooth((f-202)/14)*.7:gl?1.06:1})`}}><OffthreadVideo src={url(override.src)} startFrom={override.startFrom||0} muted style={fit}/></div></Sequence>}
 {override&&id==='JJ-005'&&f>=117&&f<218&&<CRT f={f}/>}
 {gl&&<div style={{position:'absolute',inset:0,background:'repeating-linear-gradient(0deg,transparent 0px,transparent 105px,rgba(0,255,255,.2) 108px,rgba(255,0,80,.2) 112px,transparent 124px)',mixBlendMode:'screen',transform:`translateX(${(f%3-1)*14}px)`}}/>}
 {title005&&<><Img src={staticFile('gold-plate.jpg')} style={fit}/><svg viewBox="0 0 1280 720" style={{position:'absolute',inset:0}}>{label(p.eyebrow,640,286,57,{fill:'#424536',fontWeight:700,letterSpacing:3})}{label(p.headline,640,429,150,{fill:'#424536',fontWeight:700,textLength:/[\u3400-\u9fff]/.test(p.headline)?550:480,lengthAdjust:'spacingAndGlyphs'})}</svg></>}
 {subscribe&&<><div style={{position:'absolute',inset:0,transform:`scale(${1+.26*smooth((f-1275)/7)})`,filter:`blur(${5*smooth((f-1275)/7)}px)`}}><Plate src={p.backgrounds?.subscribe||'replacement-road.mp4'} from={1066} to={1282} rate={p.backgrounds?.subscribe?1:.49}/></div><svg viewBox="0 0 1280 720" style={{position:'absolute',inset:0}}><Subscribe f={f} p={p}/></svg></>}
 {title006&&<>
 <Plate src={p.backgrounds?.question||'replacement-road.mp4'} from={1491} to={1583} rate={.9}/>
 <Plate src={p.backgrounds?.city||'replacement-city.mp4'} from={1583} to={1884} rate={p.backgrounds?.city?1:.4}/>
 <Plate src={p.backgrounds?.cash||'replacement-cash.mp4'} from={1788} to={2295} rate={p.backgrounds?.cash?1:.039} opacity={smooth((f-1788)/96)*(1-smooth((f-2240)/55))}/>
 <Plate src="replacement-road-tail.mp4" from={2240} to={2295} rate={1} opacity={smooth((f-2240)/55)}/>
 <svg viewBox="0 0 1280 720" style={{position:'absolute',inset:0}}>
 {f<1583&&label(p.question,640,364,38,{fontWeight:700,letterSpacing:9,opacity:smooth((f-1537)/8),textLength:900,lengthAdjust:'spacingAndGlyphs'})}
 {f>=1583&&f<1825&&label(p.title,640,mix(362,510,smooth((f-1755)/62)),38,{fontWeight:700,letterSpacing:10,opacity:smooth((f-1583)/5),textLength:1040,lengthAdjust:'spacingAndGlyphs'})}
 {f>=1825&&<g opacity={smooth((f-1825)/5)*(1-smooth((f-2184)/53))}>{label(p.disclaimer,640,166,86,{fontWeight:700,letterSpacing:11})}<path d="M600 211H680" stroke="white" strokeWidth="5"/>{p.lines.map((t,i)=>label(t,640,314+i*25,21,{key:i,letterSpacing:1.5}))}</g>}
 {f>=1573&&f<1597&&<><defs><radialGradient id="flare"><stop offset="0" stopColor="white"/><stop offset=".17" stopColor="white" stopOpacity=".98"/><stop offset=".45" stopColor="#ffe3f2" stopOpacity=".8"/><stop offset="1" stopColor="#ffadd7" stopOpacity="0"/></radialGradient></defs><circle cx={mix(840,570,clamp((f-1573)/24))} cy={mix(230,690,clamp((f-1573)/24))} r={mix(70,580,smooth((f-1573)/12))} fill="url(#flare)" opacity={smooth((f-1573)/8)*(1-smooth((f-1586)/11))}/></>}
 </svg></>}
 {override&&id==='JJ-005'&&f>=1120&&<AbsoluteFill style={{background:'#000',opacity:smooth((f-1120)/53)}}/>}
 </AbsoluteFill>;
}
