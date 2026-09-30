// Frame ranges are half-open at 30 fps. Full reference playback is not an editable reconstruction.
const make=(frames,title,description,cuts,names,black,defaults={},demo={})=>({frames,fps:30,startFrame:0,title,kind:'完整剪辑模块',description,mode:'hybrid-editable',defaults,demo,referenceMode:'source-replay',referenceFidelity:'720p compressed proxy; all source video frames retained, original AAC stream copied',editableFidelity:'Draft: source-native motion retained in unmodified shots; rebuilt typography/UI and replacement backgrounds are not pixel-exact',cuts,black,shots:cuts.slice(0,-1).map((from,i)=>({key:'shot'+String(i+1).padStart(2,'0'),from,to:cuts[i+1],name:names[i]||'场景'}))});
export const replacements={
 'JJ-004':make(836,'叙事蒙太奇与黑场收束','11组叙事镜头依次切换，保留末尾22帧黑场及完整声音；示例只换镜头，不额外加字。',[0,161,190,264,309,347,385,558,608,704,736,814,836],['办公室','硬币落桌','城市积水','办公室对话','ATM操作','取钞','教室离席','心理咨询','躺在座椅上','支票','点钞机','黑场'],[[814,836]],{}, {shots:{shot01:{src:'JJ-004-reference.mp4',startFrom:385}}}),
 'JJ-005':make(1182,'提问字卡·电视扫描·叙事转折','双层提问、电视曲面/扫描线/横向断裂、近景推进、两处黑场及结尾渐暗。中文例只替换开场字卡。',[0,66,117,137,157,178,218,227,253,285,333,454,530,568,600,636,669,714,810,987,1182],['提问字卡','人物近景','电视人物1','电视人物2','电视人物3','电视人物4/推进','黑场','蓝衣人物','领带人物','楼梯照片墙','走廊','桌前','楼梯酒杯','车库','钞票','公路','黑场','夕阳背影','餐厅','暗室渐黑'],[[218,227],[669,714],[1173,1182]],{eyebrow:'HOW DID THEY',headline:'DO IT?'},{eyebrow:'他们究竟',headline:'如何做到？'}),
 'JJ-006':make(2762,'完整片头组曲·故障闪回·订阅·标题·说明','保留92秒完整意群：黑场、货币叠化、色差闪回、订阅/铃铛/缩小右移、提问、标题下移、说明叠化、紫色公路与渐黑。',[0,100,224,502,671,749,857,896,934,977,1012,1066,1282,1340,1386,1491,1581,1825,2248,2667,2762],['开头黑场','城市','粉笔与货币连续叠化','两人交谈','暗室人物','沙漠公路','故障/奔跑','父子','眼镜反射','红蓝药丸','人物抉择','订阅完整动画','人群欢呼','公路推进','紫色天空人物','公路提问','城市主标题下移','现金说明/叠化','紫色公路渐黑','尾部黑场'],[[0,100],[2667,2762]],{button:'SUBSCRIBE',done:'SUBSCRIBED',question:'ARE YOU WITH ME?',title:'THE UNTOLD TRUTH ABOUT MONEY',disclaimer:'DISCLAIMER',lines:['This video was heavily inspired by the works of M J DeMarco,','as well as my own opinions and observations on how society functions on a','monetary level.','','Of course, it’s very difficult to cover this vast topic in just one YouTube','video like this, so what you are about to watch is as condensed as','I could make this information.','','Enjoy :)']},{button:'订阅频道',done:'已订阅',question:'准备好一起出发了吗？',title:'看见金钱背后的真实逻辑',disclaimer:'观看说明',lines:['这段内容，来自阅读、观察和持续思考。','我们尝试把复杂的问题，拆成可以理解的线索。','也保留每个人独立判断的空间。','','短短一段视频，无法涵盖这个话题的全部。','希望它能成为一个起点，带来新的问题，','也帮助你找到自己的答案。','','让我们开始。']}),
 'JJ-007':make(104,'黑场停顿后切入场景','前43帧黑场后硬切进入暗室镜头，保留整段声音；不擅自加片尾淡出。',[0,43,104],['黑场停顿','暗室人物'],[[0,43]],{},{shots:{shot02:{src:'JJ-004-reference.mp4',startFrom:0}}})
};
export const modules={
 'JJ-004':[{from:0,to:814,type:'montage',implementation:'Each shot replaceable, native shot motion preserved by default'},{from:814,to:836,type:'black',implementation:'Source-native; immutable time slot'}],
 'JJ-005':[{from:0,to:66,type:'two-line-title',implementation:'Editable text; replacement clean gold plate'},{from:117,to:218,type:'crt-montage',implementation:'Native reference retained by default; replaceable shots with procedural scan/break/zoom effect when replaced'},{from:218,to:227,type:'black'},{from:227,to:669,type:'montage'},{from:669,to:714,type:'black'},{from:714,to:1182,type:'montage-fade'}],
 'JJ-006':[{from:0,to:100,type:'black/faint-tail'},{from:224,to:502,type:'chalk-currency-dissolves',implementation:'Native blended background; whole shot replacement supported; underlying source layers not recoverable'},{from:852,to:1066,type:'glitch-flashbacks',implementation:'Native motion retained; replacement shots receive short RGB slice/zoom pulses'},{from:1066,to:1282,type:'subscribe',events:['appear','cursor approach','click','subscribed state','cursor to bell','bell ring','hold','collapse to icon','move right','rotate/shrink','exit']},{from:1491,to:1581,type:'question'},{from:1581,to:1825,type:'title',events:['fade in','hold','move down']},{from:1788,to:1884,type:'city-cash-dissolve'},{from:1825,to:2248,type:'disclaimer',events:['header','rule','small paragraphs','hold','fade out']},{from:2205,to:2295,type:'cash-purple-road-dissolve'},{from:2595,to:2667,type:'fade to black'},{from:2667,to:2762,type:'black-tail'}],
 'JJ-007':[{from:0,to:43,type:'black'},{from:43,to:104,type:'hard-reveal'}]
};
export function validateReplacement(id,options={}){
 const s=replacements[id],p={...s.defaults,...options};
 for(const[k,v]of Object.entries(s.defaults)){
  if(typeof v==='string'&&(typeof p[k]!=='string'||p[k].length>220))throw Error('Invalid '+k);
  if(Array.isArray(v)&&(!Array.isArray(p[k])||p[k].length!==v.length||p[k].some(x=>typeof x!=='string'||x.length>220)))throw Error('Invalid '+k);
 }
 for(const[key,v]of Object.entries(p.shots||{})){
  const sh=s.shots.find(s=>s.key===key);
  if(!sh||s.black.some(([a,b])=>sh.from>=a&&sh.to<=b))throw Error('Invalid/black shot '+key);
  if(!v.src||!Number.isInteger(v.startFrom??0)||(v.startFrom??0)<0)throw Error('Invalid media '+key);
  if(p.native!==true&&((id==='JJ-005'&&key==='shot01')||(id==='JJ-006'&&['shot12','shot16','shot17','shot18','shot19'].includes(key))))throw Error('This shot contains a rebuilt overlay. Use backgrounds fields or native:true for whole-shot replacement.');
 }
 const allowed=id==='JJ-006'?['subscribe','question','city','cash']:[];
 for(const[k,v]of Object.entries(p.backgrounds||{}))if(!allowed.includes(k)||typeof v!=='string'||!v.length)throw Error('Invalid background '+k);
 return p;
}
