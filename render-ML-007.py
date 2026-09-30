# -*- coding: utf-8 -*-
import sys,json,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/'deps'))
import cv2,numpy as np
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parent
OUT=Path(sys.argv[2]).resolve().parent if len(sys.argv)>2 else ROOT
OUT.mkdir(parents=True,exist_ok=True)
TARGET=Path(sys.argv[2]).resolve() if len(sys.argv)>2 else OUT/'ML-007-demo.mp4'
def render(options=None):
    options=options or {};m=json.loads((ROOT/'ML-007.json').read_text());N=m['frames']
    dec=subprocess.Popen(['ffmpeg','-v','error','-i',str(ROOT/m['reference']),'-an','-f','rawvideo','-pix_fmt','rgb24','-'],stdout=subprocess.PIPE)
    enc=subprocess.Popen(['ffmpeg','-v','error','-f','rawvideo','-pix_fmt','rgb24','-s','1280x720','-r','30','-i','pipe:0','-i',str(ROOT/m['audio']),'-map','0:v','-map','1:a','-frames:v',str(N),'-c:v','libx264','-threads','2','-preset','veryfast','-crf','18','-pix_fmt','yuv420p','-c:a','copy','-movflags','+faststart','-y',str(TARGET)],stdin=subprocess.PIPE)
    font=ImageFont.truetype('/System/Library/Fonts/STHeiti Medium.ttc',34)
    modified=[]
    for f in range(N):
        raw=dec.stdout.read(1280*720*3);a=np.frombuffer(raw,np.uint8).reshape(720,1280,3).copy()
        if 0<=f<=178:
            # Only the inside of the existing button is changed. Cursor, bell,
            # spinning logo, the landscape and the shrink-away tail stay native.
            red=f<29
            if red:
                region=a[580:695,525:755];r=region[:,:,0].astype(float);g=region[:,:,1].astype(float)
                mask=(r>150)&(g<75)
                yy,xx=np.where(mask)
                if len(xx)>100:
                    top=580+int(yy.min());bottom=580+int(yy.max());left=525+int(xx.min());right=525+int(xx.max())
                else:top=bottom=0;left=right=0
            else:left,right,top,bottom=531,749,595,666
            if bottom-top>12:
                box=[max(left+6,538),max(top+5,top),min(right-6,743),min(bottom-5,661)]
                x0,y0,x1,y1=box
                if y1>y0:
                    bg=np.median(a[y0:y1,x0:x0+3],axis=(0,1)).astype(np.uint8)
                    original=a[y0:y1,x0:x1].copy()
                    a[y0:y1,x0:x1]=bg
                    im=Image.fromarray(a);d=ImageDraw.Draw(im)
                    text=options.get('subscribe' if red else 'subscribed','订阅' if red else '已订阅')
                    b=font.getbbox(text);x=640-font.getlength(text)/2;y=(top+bottom)/2-(b[1]+b[3])/2
                    d.text((x,y),text,font=font,fill=(255,255,255) if red else (114,114,114));a=np.asarray(im).copy()
                    # Native hand occludes the button during the click. Keep its
                    # lower connected silhouette instead of drawing over it.
                    if 17<=f<=51:
                        roi=original;gray=cv2.cvtColor(roi,cv2.COLOR_RGB2GRAY)
                        seed=(gray<45).astype(np.uint8)
                        num,lbl,stats,cent=cv2.connectedComponentsWithStats(seed,8)
                        hand=np.zeros_like(seed)
                        for k in range(1,num):
                            xk,yk,wk,hk,area=stats[k]
                            if yk+hk>=seed.shape[0]-1 and area>4:hand[lbl==k]=1
                        hand=cv2.dilate(hand,np.ones((5,5),np.uint8))
                        a[y0:y1,x0:x1][hand>0]=original[hand>0]
                    modified.append(f)
        if f==179:
            # Last three Latin letters remain visible for a single frame after
            # the circle has swept over the Chinese label's shorter extent.
            a[612:656,677:742]=a[602:603,677:742]
            modified.append(f)
        enc.stdin.write(a.tobytes())
    enc.stdin.close();dec.stdout.close();assert enc.wait()==0 and dec.wait()==0
    (OUT/'ML-007-rebuild.json').write_text(json.dumps({'id':'ML-007','status':'candidate-awaiting-dense-QC','frames':N,'fps':30,'slots':{'subscribe':'订阅','subscribed':'已订阅'},'modifiedFrames':modified,'limits':['Button caption is reconstructed. Native cursor overlap requires frame-by-frame review.','All motion outside the existing button interior and original mixed audio are retained.']},ensure_ascii=False,indent=2))
    print('ML-007 rendered',len(modified),flush=True)
if __name__=='__main__':
    options=json.loads(Path(sys.argv[1]).read_text()) if len(sys.argv)>1 else {}
    if set(options)-{'subscribe','subscribed'}:raise ValueError('Unknown slot')
    if any(not isinstance(v,str) or not 1<=len(v)<=4 for v in options.values()):raise ValueError('Labels need 1-4 characters')
    render(options)
