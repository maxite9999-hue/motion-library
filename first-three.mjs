// Pure, deterministic production renderer. Shared by preview and MP4 export.
export const specs={
 'JJ-012':{frames:534,fps:30,startFrame:9891,title:'数字变化与时间成本',defaults:{income:20,currency:'$',rateUnit:'/hr',incomeLabel:'INCOME',hours:40,hoursLabel:'HOURS',periodLabel:'WEEK',years:24,yearsLabel:'YEARS',target:'$1,000,000'},demo:{income:50,currency:'¥',rateUnit:'/时',incomeLabel:'时薪',hours:30,hoursLabel:'小时',periodLabel:'每周',years:12,yearsLabel:'年',target:'¥1,000,000'}},
 'JJ-019':{frames:168,fps:30,startFrame:15732,title:'倾斜词组逐行拼接',defaults:{headline:'LOOK FOR',line2:'PROBLEMS',connector:'&',line3:'SOLUTIONS'},demo:{headline:'寻找',line2:'真正的问题',connector:'和',line3:'可行的解法'}},
 'JJ-026':{frames:244,fps:30,startFrame:26076,title:'黑底结论逐行出现',defaults:{lines:['STOP CHASING MONEY','CHASE PROBLEMS','FIND SOLUTIONS TO THOSE PROBLEMS']},demo:{lines:['别再堆砌特效','让画面服务表达','让每一次变化都有意义']}}
};
const clamp=x=>Math.max(0,Math.min(1,x));
const ease=x=>1-(1-clamp(x))**3;
const smooth=x=>{x=clamp(x);return x*x*(3-2*x)};
const mix=(a,b,p)=>a+(b-a)*p;
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'}[c]));
const cjk=s=>/[\u3400-\u9fff]/.test(s);
const font=s=>cjk(s)?'PingFang SC,Microsoft YaHei,sans-serif':'Arial Narrow,Arial,sans-serif';
function text(s,x,y,size,{weight=400,anchor='start',width,opacity=1,spacing=0}={}){if(width&&cjk(s))width=Math.min(width,String(s).length*size+spacing*(String(s).length-1));return `<text x="${x}" y="${y}" fill="currentColor" font-family="${font(s)}" font-size="${size}" font-weight="${weight}" text-anchor="${anchor}" letter-spacing="${spacing}" opacity="${opacity}" ${width?`textLength="${width}" lengthAdjust="spacingAndGlyphs"`:''}>${esc(s)}</text>`}
function group(body,transform='',opacity=1){return `<g transform="${transform}" opacity="${opacity}">${body}</g>`}
function gold(t,plate){return `<rect width="1280" height="720" fill="#edab25"/>${plate?`<image href="${esc(plate)}" width="1280" height="720"/>`:''}<ellipse cx="${700+120*Math.sin(t*.2)}" cy="130" rx="420" ry="180" fill="#ffd289" opacity=".035" filter="url(#soft)"/>`}
export function validate(id,options={}){if(!specs[id])throw Error('Unknown template: '+id);const p={...specs[id].defaults,...options};if(id==='JJ-012'){for(const key of ['income','hours','years'])if(!Number.isFinite(p[key])||p[key]<0||p[key]>999)throw Error(key+' must be 0..999');if(String(p.target).length>16)throw Error('target too long')}if(id==='JJ-019'){for(const k of ['headline','line2','line3'])if(!p[k]||String(p[k]).length>30)throw Error(k+' must be 1..30 characters')}if(id==='JJ-026'&&(!Array.isArray(p.lines)||p.lines.length!==3||p.lines.some(x=>!x||String(x).length>60)))throw Error('three short lines required');return p}
export function renderSVG(id,frame,options={},assets={}){
 const spec=specs[id],p=validate(id,options),f=Math.max(0,Math.min(spec.frames-1,frame)),t=f/30;
 let body='';
 if(id==='JJ-012'){
  body=gold(t,assets.gold);
  if(t<2.97){
   const e=ease((t-.28)/.72),n=Math.round(p.income*ease((t-.28)/.65)),scale=mix(2.6,1,e),rot=mix(13,0,e),exit=ease((t-2.77)/.2);
   const number=p.currency+n,amount=text(number,-195,30,148,{weight:700,width:240})+text(p.rateUnit,55,30,100,{weight:700,width:155})+text(p.incomeLabel,-185,-117,31);
   body+=group(amount,`translate(640 390) rotate(${rot}) scale(${scale*.9*(1+exit*1.8)})`,1-exit);
   if(t<.45)body+=`<path d="M0 0 H1280 V${80*(1-e)} L0 ${150*(1-e)}Z" fill="#141414"/>`;
  }else if(t<5.33){
   const d=t-2.97,ent=ease(d/.22),out=ease((t-4.97)/.36),s=(.75+.25*ent)*(1+out*4);
   let h=text(String(p.hours),-157,62,248,{weight:700,width:267})+group(text(p.hoursLabel,0,0,47,{weight:700,width:176}), 'translate(117 -131) rotate(90)',ease((d-.08)/.22))+text(p.periodLabel,0,135,69,{weight:700,anchor:'middle',spacing:14,opacity:ease((d-.53)/.3)});
   body+=group(h,`translate(640 373) scale(${s})`,1-out);
  }else if(t<7.32){
   const d=t-5.33,enter=ease(d/.65),out=ease((t-7.06)/.26),radius=280;
   let clock=`<circle r="${radius}" fill="none" stroke="#090a09" stroke-width="11" stroke-dasharray="${2*Math.PI*radius}" stroke-dashoffset="${2*Math.PI*radius*(1-enter)}" transform="rotate(-90)"/>`;
   for(let i=0;i<12;i++){const a=i*Math.PI/6;clock+=`<line x1="${Math.sin(a)*239}" y1="${-Math.cos(a)*239}" x2="${Math.sin(a)*(i%3===0?213:226)}" y2="${-Math.cos(a)*(i%3===0?213:226)}" stroke="#090a09" stroke-width="${i%3===0?15:10}" stroke-linecap="round" opacity="${ease((d-i*.014)/.25)}"/>`}
   const theta=mix(-100,200,enter)+d*65;
   clock+=group('<line y2="-214" stroke="#090a09" stroke-width="10" stroke-linecap="round"/>',`rotate(${theta})`)+group('<line y2="-127" stroke="#090a09" stroke-width="12"/>',`rotate(${theta*.43})`);
   clock+=text(String(Math.round(p.years*enter)),0,45,310,{weight:700,anchor:'middle',width:300})+text(p.yearsLabel,0,146,98,{weight:700,anchor:'middle',opacity:ease((d-.55)/.25),width:300});
   body+=group(clock,`translate(${640-out*1080} 360) scale(.99)`,1-out*.35);
  }else{
   const d=t-7.32,reveal=clamp(d/.72),shown=Math.floor(p.target.length*reveal),label=p.target.slice(0,shown)+(shown<p.target.length?'_':''),exit=ease((t-17.1)/.6),breath=1+.008*Math.sin(d*1.4);
   body+=group(text(label,0,0,191,{weight:700,anchor:'middle',width:Math.min(1020,Math.max(110,label.length*92))}),`translate(640 429) rotate(${-2.1+.4*Math.sin(d*.9)}) scale(${breath*(1-exit*.43)})`);
  }
 }else if(id==='JJ-019'){
  body=gold(t,assets.gold);
  const angle=mix(-15,3,smooth((t-.3)/5)),sx=mix(1.16,1,ease(t/.35)),x=240+15*Math.sin(t*.9),y=353+5*Math.sin(t*1.1);
  const a=ease(t/.2),b=ease((t-.43)/.25),c=ease((t-1.17)/.2),d=ease((t-2.22)/.35);
  let lines=text(p.headline,0,0,cjk(p.headline)?140:160,{weight:700,width:810,opacity:a,spacing:8})+text(p.line2,0,99,cjk(p.line2)?94:101,{width:604,opacity:b,spacing:5})+text(p.connector,0,202,cjk(p.connector)?90:137,{weight:700,width:80,opacity:c})+text(p.line3,94,200,cjk(p.line3)?90:101,{width:630,opacity:d,spacing:5});
  body+=group(lines,`translate(${x} ${y}) rotate(${angle}) scale(${sx})`);
 }else{
  body='<rect width="1280" height="720" fill="#000"/>';
  p.lines.forEach((line,i)=>{const a=smooth((t-[.13,1.8,2.66][i])/1.25),size=cjk(line)?37:38,maxWidth=850,estimated=line.length*(cjk(line)?37:19);body+=text(line,211,313+i*45,size,{opacity:a,width:estimated>maxWidth?maxWidth:undefined,spacing:cjk(line)?1:1.15})});
 }
 return `<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720" style="color:${id==='JJ-026'?'#eeeeec':'#090a09'}"><defs><filter id="soft"><feGaussianBlur stdDeviation="70"/></filter></defs>${body}</svg>`;
}
