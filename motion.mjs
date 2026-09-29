export const defaults={unit:'$1,000,000',ten:'$10 MILLION',hundred:'$100 MILLION',accent:'#e4a321'};
const ease=x=>1-Math.pow(1-Math.max(0,Math.min(1,x)),3);
const esc=x=>String(x).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;');
export function renderSVG(t,options={}){
 const p={...defaults,...options};t=Math.max(0,Math.min(14,t));
 const frame=Math.floor(t*30+1e-6);
 if((frame>=204&&frame<218)||(frame>=320&&frame<332))return '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720"><rect width="1280" height="720" fill="black"/></svg>';
 const stage=frame<218?0:frame<332?1:2,dt=t-[0,218/30,332/30][stage];
 const count=[1,10,100][stage],radius=[43,43,24][stage];
 let dots='';
 for(let i=0;i<count;i++){
  const x=stage===0?640:stage===1?640+(i%5-2)*110:694+(i%10-4.5)*69;
  const y=stage===0?360:stage===1?430-Math.floor(i/5)*110:357+(Math.floor(i/10)-4.5)*69;
  const a=stage===0?1:ease((dt-i*(stage===1?.16:.014))/.13);
  dots+=`<circle cx="${x}" cy="${y}" r="${radius}" fill="#101010" opacity="${a}"/>`;
 }
 let label=stage===0?`<text x="640" y="483" text-anchor="middle" font-size="48" opacity="${ease((dt-1.8)/.7)}">= ${esc(p.unit)}</text>`:stage===1?`<text x="375" y="259" font-size="67" opacity="${ease((dt-.6)/.6)}">${esc(p.ten)}</text>`:`<text transform="translate(322 667) rotate(-90)" font-size="65" opacity="${ease((dt-.45)/.55)}">${esc(p.hundred)}</text>`;
 return `<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720"><defs><radialGradient id="bg" cx="${62+Math.sin(t*.3)*6}%" cy="42%" r="80%"><stop stop-color="#ffd281"/><stop offset=".5" stop-color="${esc(p.accent)}"/><stop offset="1" stop-color="#bc8518"/></radialGradient><filter id="blur"><feGaussianBlur stdDeviation="65"/></filter><filter id="grain"><feTurbulence type="fractalNoise" baseFrequency=".75" numOctaves="2" seed="5"/><feColorMatrix type="saturate" values="0"/></filter></defs><rect width="1280" height="720" fill="url(#bg)"/><g filter="url(#blur)" opacity=".23" fill="#fff3c5"><ellipse cx="${850+Math.sin(t*.2)*90}" cy="240" rx="220" ry="220"/><ellipse cx="${370+Math.cos(t*.18)*100}" cy="660" rx="300" ry="120"/></g><rect width="1280" height="720" filter="url(#grain)" opacity=".07"/>${dots}<g fill="white" font-family="Arial Narrow,Helvetica Neue,Arial,sans-serif" font-weight="400">${label}</g></svg>`;
}
