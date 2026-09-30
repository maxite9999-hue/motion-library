"""Fixed native motion + localized, replaceable text. Not vector reconstruction.
Usage: python3 render-faithful.py recipe.json options.json output.mp4 source_dir
Requires Pillow, numpy, opencv-python and ffmpeg. No generated extra headings.
"""
from pathlib import Path
import sys,json,subprocess as sp,functools,base64,io
import numpy as np
from PIL import Image,ImageDraw,ImageFont
try:import cv2
except ImportError:
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'work/cn-rebuild/deps'));import cv2
FONT_PATH=next(Path('/System/Library/AssetsV2').glob('**/PingFang.ttc'),None)
@functools.lru_cache(2)
def face(weight):
    return ImageFont.truetype(str(FONT_PATH),180,index=11 if weight=='Medium' else 15) if FONT_PATH else ImageFont.truetype(f'/System/Library/Fonts/STHeiti {weight}.ttc',180,index=1)

@functools.lru_cache(512)
def glyph(s,w,h,weight,shown=None):
    f=face(weight)
    b=f.getbbox(s)
    common_h=max(1,b[3]-b[1]);advance=sum(f.getlength(c) for c in s)
    gap=max(0,(w*common_h/max(1,h)-advance)/max(1,len(s)-1))
    im=Image.new('L',(round(advance+gap*max(0,len(s)-1))+12,common_h+4));d=ImageDraw.Draw(im);x=4
    # Every character shares one baseline and cap-height coordinate system.
    # In particular, the single stroke 一 must never be stretched to cap height.
    positions=[]
    for c in s:
        positions.append((x,c))
        d.text((x,2-b[1]),c,font=f,fill=255);x+=f.getlength(c)+gap
    bounds=im.getbbox()
    if shown is not None:
        im=Image.new('L',im.size);d=ImageDraw.Draw(im)
        for x,c in positions[:shown]:d.text((x,2-b[1]),c,font=f,fill=255)
    if bounds:im=im.crop(bounds)
    return np.asarray(im.resize((max(1,w),max(1,h)),Image.Resampling.LANCZOS))

def measure(native,tr,f):
    x0,y0,x1,y1=tr['roi'];crop=native[y0:y1,x0:x1];ch=crop[:,:,2]
    dark=tr['ink']=='dark';kernel=cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(41,41))
    if tr['ink'] in ('red','green','gold'):
        rgb=crop.astype(float);r,g,b=rgb[:,:,0],rgb[:,:,1],rgb[:,:,2]
        if tr['ink']=='red':
            hsv=cv2.cvtColor(crop,cv2.COLOR_RGB2HSV);mask=((hsv[:,:,0]<8)|(hsv[:,:,0]>172))&(hsv[:,:,1]>80)&(r>65)&(g<75)&(b<75)
        elif tr['ink']=='green':mask=(g>r*1.25)&(g>b*1.2)&(g>60)
        else:mask=(r>b*1.5)&(g>b*1.4)&(r>tr.get('redFloor',75))&(g>tr.get('greenFloor',70))
    elif dark:
        # Gold plate: foreground is dark in all channels, never the smoke itself.
        score=cv2.morphologyEx(cv2.cvtColor(crop,cv2.COLOR_RGB2GRAY),cv2.MORPH_BLACKHAT,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(81,81)))
        mask=(score>tr.get('contrastThreshold',8))&(crop[:,:,0]<tr.get('redCeiling',155))&(crop[:,:,1]<tr.get('greenCeiling',150))
        if tr.get('excludeRed'):mask&=(crop[:,:,0].astype(float)<crop[:,:,1]*1.3+12)
    else:
        score=cv2.morphologyEx(ch,cv2.MORPH_TOPHAT,kernel)
        rgb=crop.astype(np.float32)
        mask=(score>tr.get('contrastThreshold',8))&(rgb[:,:,0]>tr.get('redFloor',155))&(rgb[:,:,1]>tr.get('greenFloor',125))&(rgb[:,:,2]>rgb[:,:,1]*.76)
    if 'band' in tr:
        cx,cy,angle,halfheight=tr['band'];yy,xx=np.mgrid[y0:y1,x0:x1];rad=np.deg2rad(angle);perp=-(xx-cx)*np.sin(rad)+(yy-cy)*np.cos(rad);mask&=np.abs(perp)<halfheight
    count,labels,stats,centroids=cv2.connectedComponentsWithStats(mask.astype(np.uint8),8)
    good=np.zeros(mask.shape,np.uint8)
    for i in range(1,count):
        if tr.get('rejectBorder'):
            sx,sy,sw,sh,_=stats[i]
            if sx<1 or sy<1 or sx+sw>=mask.shape[1]-1 or sy+sh>=mask.shape[0]-1:continue
        if stats[i,cv2.CC_STAT_AREA]>=tr.get('minArea',10):good[labels==i]=255
    ys,xs=np.where(good)
    if len(xs)<tr.get('minPixels',65):return None
    bbox=[int(xs.min()+x0),int(ys.min()+y0),int(xs.max()+x0+1),int(ys.max()+y0+1)]
    colors=crop[good>0];color=np.percentile(colors,35 if dark else 85,axis=0).astype(np.uint8)
    return bbox,good,color

@functools.lru_cache(128)
def decode_mask(value):
    return np.asarray(Image.open(io.BytesIO(base64.b64decode(value))).convert('L'))

@functools.lru_cache(8)
def decode_plate(value):
    return np.asarray(Image.open(io.BytesIO(base64.b64decode(value))).convert('RGB'))

def keyed(tr,f):
    if not tr.get('geometry'):return tr
    points=tr['geometry'];p=max((p for p in points if p['f']<=f),key=lambda p:p['f'],default=points[0]);q=min((p for p in points if p['f']>=f),key=lambda p:p['f'],default=points[-1]);a=(f-p['f'])/max(1,q['f']-p['f']);v=dict(tr)
    for k in ('roi','lockedBox'):
        if k in p:v[k]=[round(x+(y-x)*a) for x,y in zip(p[k],q[k])]
    for k in ('blurY','opacity','revealFraction'):
        if k in p and k in q:v[k]=p[k]+(q[k]-p[k])*a
    return v

def text_box(tr,value,box):
    x,y,r,b=box
    if tr.get('naturalWidth'):
        ff=face(tr.get('weight','Light'));bb=ff.getbbox(value);w=min(r-x,round((b-y)*ff.getlength(value)/max(1,bb[3]-bb[1])))
        x+=round((r-x-w)*tr.get('anchor',.5));r=x+w
    return x,y,r,b

def frame(native,tracks,options,f):
    out=native.copy();allowed=np.zeros(native.shape[:2],bool);records=[];layers=[]
    for tr in tracks:
        if not tr['start']<=f<tr['end']:continue
        tr=keyed(tr,f)
        if tr.get('affineMask'):
            mat=np.array(tr['poses'][str(f)],np.float32)
            silhouette=cv2.warpAffine(decode_mask(tr['affineMask']),mat,(1280,720))
            if tr.get('adaptiveCleanup'):
                bx,by,br,bb=tr['canonicalBox'];region=np.zeros((720,1280),np.uint8);region[max(0,by-5):min(720,bb+5),max(0,bx-12):min(1280,br+12)]=255
                region=cv2.warpAffine(region,mat,(1280,720))>0
                fg=(native[:,:,0]<210)&(native[:,:,1]<190)&region
                silhouette=np.maximum(silhouette,fg.astype(np.uint8)*255)
            pad=cv2.dilate(silhouette,np.ones((9,9),np.uint8))
            ys,xs=np.where(pad)
            if not len(xs):continue
            x0=max(0,int(xs.min())-12);y0=max(0,int(ys.min())-12);x1=min(1280,int(xs.max())+13);y1=min(720,int(ys.max())+13)
            crop=native[y0:y1,x0:x1];pm=pad[y0:y1,x0:x1]
            clean=cv2.inpaint(crop,pm,9,cv2.INPAINT_TELEA)
            core=cv2.erode(silhouette[y0:y1,x0:x1],np.ones((3,3),np.uint8))>180
            if not np.any(core):continue
            contrast=clean.astype(float).mean(2)-crop.astype(float).mean(2)
            opacity=float(np.clip(np.percentile(contrast[core],70)/max(1,np.median(clean[core])-25),0,1))
            region=out[y0:y1,x0:x1];region[pm>0]=clean[pm>0];allowed[y0:y1,x0:x1]|=pm>0
            x,y,r,b=tr['canonicalBox'];val=options.get(tr['key'],tr['text']);h=b-y;w=r-x
            if tr.get('naturalWidth'):
                ff=face(tr.get('weight','Light'));bb=ff.getbbox(val);w=min(w,round(h*ff.getlength(val)/max(1,bb[3]-bb[1])))
            plane=np.zeros((720,1280),np.uint8);plane[y:b,x:x+w]=glyph(val,w,h,tr.get('weight','Light'))
            a=cv2.warpAffine(plane,mat,(1280,720)).astype(float)/255*opacity
            layers.append((0,0,1280,720,a,np.array(tr.get('color',[25,25,24]))));allowed|=a>0
            records.append({'key':tr['key'],'affine':mat.tolist(),'opacity':opacity});continue
        if tr.get('groupLines'):
            found=measure(native,tr,f)
            if found is None:continue
            _,mask,color=found;x0,y0,x1,y1=tr['roi'];yy,xx=np.where(mask)
            center,size,theta=cv2.minAreaRect(np.column_stack((xx+x0,yy+y0)).astype(np.float32))
            if size[1]>size[0]:theta-=90
            if abs(theta)>30:theta=0
            mat=cv2.getRotationMatrix2D(center,theta,1);inv=cv2.invertAffineTransform(mat)
            full=np.zeros((720,1280),np.uint8);full[y0:y1,x0:x1]=mask
            straight=cv2.warpAffine(full,mat,(1280,720));counts=np.count_nonzero(straight,axis=1);projection=counts>max(10,counts.max()*.08)
            runs=[];last=None
            for y in np.where(projection)[0]:
                if last is None or y-last>2:runs.append([int(y),int(y)])
                else:runs[-1][1]=int(y)
                last=y
            runs=[(a,b) for a,b in runs if b-a>8]
            pad=cv2.dilate(mask,np.ones((13,13),np.uint8));out[y0:y1,x0:x1]=cv2.inpaint(out[y0:y1,x0:x1],pad,11,cv2.INPAINT_TELEA);allowed[y0:y1,x0:x1]|=pad>0
            plane=np.zeros((720,1280),np.uint8)
            for i,(a,b) in enumerate(runs[:len(tr['groupLines'])]):
                row=tr['groupLines'][i];_,xs=np.where(straight[a:b+1]);left,right=int(xs.min()),int(xs.max()+1)
                if f<row.get('start',tr['start']):continue
                val=options.get(row['key'],row['text'])
                if row.get('prefixUntil',0)>f:val=row.get('prefix','')
                h=b-a+1;ff=face(row.get('weight','Light'));bb=ff.getbbox(val);nw=min(right-left,round(h*ff.getlength(val)/max(1,bb[3]-bb[1])));g=glyph(val,nw,h,row.get('weight','Light'));plane[a:b+1,left:left+nw]=g
                records.append({'key':row['key'],'box':[left,a,right,b+1],'angle':float(theta)})
            a=cv2.warpAffine(plane,inv,(1280,720)).astype(float)/255;layers.append((0,0,1280,720,a,color));allowed|=a>0;continue
        if tr.get('fixedMask'):
            x0,y0,x1,y1=tr['roi'];crop=native[y0:y1,x0:x1];mask=decode_mask(tr['fixedMask']);pad=cv2.dilate(mask,np.ones((7,7),np.uint8));clean=cv2.inpaint(crop,pad,7,cv2.INPAINT_TELEA)
            # A source-derived silhouette also catches the faint first/last glyphs.
            # Estimate contrast on its eroded interior, not on moving background.
            core=cv2.erode(mask,np.ones((3,3),np.uint8))>0
            if not np.any(core):core=mask>0
            delta=crop.astype(float)-clean.astype(float)
            signal=delta[core].mean(1);strength=np.percentile(signal,75)
            opacity=float(np.clip(strength/max(1,tr.get('fullContrast',180)),0,1))
            out[y0:y1,x0:x1]=clean;allowed[y0:y1,x0:x1]|=pad>0
            val=options.get(tr['key'],tr['text']);x,y,r,b=text_box(tr,val,tr['lockedBox']);a=glyph(val,r-x,b-y,tr.get('weight','Light')).astype(float)/255*opacity
            color=np.array(tr.get('color',[245,245,240]));layers.append((x,y,r,b,a,color));allowed[y:b,x:r]|=a>0
            records.append({'key':tr['key'],'box':[x,y,r,b],'opacity':opacity});continue
        if tr.get('fadingPlate'):
            x0,y0,x1,y1=tr['roi'];crop=native[y0:y1,x0:x1].astype(np.float32);hh,ww=crop.shape[:2]
            u=np.linspace(0,1,ww)[None,:,None];v=np.linspace(0,1,hh)[:,None,None]
            corners=(1-v)*((1-u)*crop[0,0]+u*crop[0,-1])+v*((1-u)*crop[-1,0]+u*crop[-1,-1])
            plate=np.clip((1-v)*crop[0:1]+v*crop[-1:]+(1-u)*crop[:,0:1]+u*crop[:,-1:]-corners,0,255)
            if tr.get('flatPlate') or f>=tr.get('flatFrom',10**9):
                # White paper must not stretch neighboring line strokes through
                # a Coons surface when the scroll brings them across its edges.
                paper=np.percentile(crop.reshape(-1,3),75,axis=0)
                plate=np.broadcast_to(paper,crop.shape).astype(np.float32)
            if 'rowPlateSample' in tr:
                sx,sr=tr['rowPlateSample'];colors=np.median(native[y0:y1,sx:sr],axis=1)
                plate=np.broadcast_to(colors[:,None,:],crop.shape).astype(np.float32)
            if tr.get('goldPlate'):
                # Fit the local source gold lighting, excluding white and dark ink.
                yy,xx=np.mgrid[0:hh,0:ww];xx=xx/max(1,ww-1);yy=yy/max(1,hh-1)
                basis=np.stack([np.ones_like(xx),xx,yy,xx*yy,xx*xx,yy*yy],axis=-1)
                good=(crop[:,:,0]>170)&(crop[:,:,1]>100)&(crop[:,:,2]<100)
                sampled=good&((np.indices(good.shape).sum(0)%7)==0)
                if sampled.sum()>30:
                    coeff=np.linalg.lstsq(basis[sampled],crop[sampled],rcond=None)[0]
                    plate=np.clip(basis@coeff,0,255).astype(np.float32)
            # Measure source fade against the smooth plate, including faint frames
            # that ordinary OCR and hard foreground thresholds miss.
            dark=tr['ink']=='dark'
            residual=plate.mean(2)-crop.mean(2) if dark else crop[:,:,2]-plate[:,:,2]
            divisor=np.median(plate.mean(2))-50 if dark else 245-np.median(plate[:,:,2])
            opacity=float(np.clip(np.percentile(residual,99)/max(1,divisor),0,1))
            if 'opacity' in tr:opacity=tr['opacity']
            out[y0:y1,x0:x1]=plate.astype(np.uint8);allowed[y0:y1,x0:x1]=True
            val=options.get(tr['key'],tr['text']);x,y,r,b=text_box(tr,val,tr['lockedBox']);fraction=tr.get('revealFraction',1);shown=max(1,int(len(val)*fraction)) if fraction<.99 else None;a=glyph(val,r-x,b-y,tr.get('weight','Light'),shown).astype(np.float32)/255*opacity
            color=np.array(tr.get('color',[50,50,47] if dark else [245,240,223]))
            sigma=tr.get('blurY',0)
            if sigma>.1:
                plane=np.zeros((720,1280),np.float32);plane[y:b,x:r]=a;kernel=max(3,int(sigma*6)|1)
                plane=cv2.GaussianBlur(plane,(1,kernel),sigmaX=.01,sigmaY=sigma,borderType=cv2.BORDER_CONSTANT)
                layers.append((0,0,1280,720,plane,color));allowed|=plane>0
            else:layers.append((x,y,r,b,a,color));allowed[y:b,x:r]|=a>0
            records.append({'key':tr['key'],'box':[x,y,r,b],'opacity':opacity});continue
        if tr.get('aboveDotArray'):
            dark=(native[:,:,0]<105)&(native[:,:,1]<95)&(native[:,:,2]<95)
            count,labels,stats,_=cv2.connectedComponentsWithStats(dark.astype(np.uint8),8)
            dots=[s for s in stats[1:] if 8<=s[cv2.CC_STAT_AREA]<=2000 and .45<s[2]/max(1,s[3])<1.8]
            if not dots:continue
            left=min(s[0] for s in dots);top=min(s[1] for s in dots);right=max(s[0]+s[2] for s in dots)
            hh=round((right-left)*.21)
            tr=dict(tr,roi=[max(0,left-18),max(0,top-round(hh*1.6)),min(1280,right+18),max(1,top-5)])
        found=measure(native,tr,f)
        if found is None:continue
        box,mask,color=found
        if box[2]-box[0]<tr.get('minBoxWidth',0):continue
        x0,y0,x1,y1=tr['roi'];mp=tr.get('maskPad',11);pad=cv2.dilate(mask,np.ones((mp,mp),np.uint8))
        # Only masked source glyphs are repaired; no full-screen generic plate.
        crop=out[y0:y1,x0:x1];crop[:]=cv2.inpaint(crop,pad,11,cv2.INPAINT_TELEA);allowed[y0:y1,x0:x1]|=pad>0
        if tr.get('portraitPlate'):
            px,py,pr,pb=tr['plateBox'];plate=decode_plate(tr['portraitPlate']);sx=max(px,x0);sy=max(py,y0);sr=min(pr,x1);sb=min(pb,y1)
            active=pad[sy-y0:sb-y0,sx-x0:sr-x0]>0
            out[sy:sb,sx:sr][active]=plate[sy-py:sb-py,sx-px:sr-px][active]
        if tr.get('autoRotate'):
            yy,xx=np.where(mask);pts=np.column_stack((xx+x0,yy+y0)).astype(np.float32);center,size,theta=cv2.minAreaRect(pts)
            rw,rh=size
            if rh>rw:rw,rh=rh,rw;theta-=90
            if theta<-90:theta+=180
            if theta>90:theta-=180
            if 'angleOverride' in tr:theta=tr['angleOverride']
            rw=max(2,round(rw));rh=max(2,round(rh));value=options.get(tr['key'],tr['text'])
            if tr.get('naturalWidth'):
                ff=face(tr.get('weight','Medium'));bb=ff.getbbox(value);nw=min(rw,round(rh*ff.getlength(value)/max(1,bb[3]-bb[1])));shift=(rw-nw)/2;rad=np.deg2rad(theta);center=(center[0]-shift*np.cos(rad),center[1]-shift*np.sin(rad));rw=nw
            a=glyph(value,rw,rh,tr.get('weight','Medium'))
            rad=np.deg2rad(theta);u=np.array([np.cos(rad),np.sin(rad)]);v=np.array([-np.sin(rad),np.cos(rad)]);c=np.array(center)
            dst=np.float32([c-u*rw/2-v*rh/2,c+u*rw/2-v*rh/2,c-u*rw/2+v*rh/2]);mat=cv2.getAffineTransform(np.float32([[0,0],[rw,0],[0,rh]]),dst)
            a=cv2.warpAffine(a,mat,(1280,720),flags=cv2.INTER_LINEAR).astype(float)/255;layers.append((0,0,1280,720,a,color));allowed|=a>0
            records.append({'key':tr['key'],'angle':float(theta),'size':[rw,rh],'center':list(center)});continue
        box=np.array(box,dtype=int);angle=tr.get('angle',0);reveal=1.
        if 'fullBox' in tr and f<tr.get('revealEnd',tr['start']):
            target=np.array(tr['fullBox'])
            reveal=np.clip((target[3]-box[1])/max(1,target[3]-target[1]) if angle else (box[2]-target[0])/max(1,target[2]-target[0]),0,1);box=target
        elif 'lockedBox' in tr:box=np.array(tr['lockedBox'])
        if tr.get('naturalWidth') and not angle:box=np.array(text_box(tr,options.get(tr['key'],tr['text']),box))
        x,y,r,b=box;w,h=r-x,b-y
        if w<2 or h<2:continue
        value=options.get(tr['key'],tr['text'])
        if 'revealFraction' in tr:reveal=tr['revealFraction']
        shown=max(1,int(len(value)*reveal)) if reveal<.99 else None
        a=glyph(value,h if angle else w,w if angle else h,tr.get('weight','Light'),shown)
        if angle:a=np.rot90(a,-1 if angle<0 else 1)
        tile=np.broadcast_to(color,(h,w,3)).copy()
        xa=max(0,x);ya=max(0,y);xb=min(1280,r);yb=min(720,b)
        alpha=a[ya-y:yb-y,xa-x:xb-x].astype(np.float32)/255
        if alpha.size:
            layers.append((xa,ya,xb,yb,alpha,color))
            allowed[ya:yb,xa:xb]|=alpha>0
        records.append({'key':tr['key'],'box':box.tolist(),'reveal':float(reveal)})
    for x,y,b,c,a,color in layers:
        out[y:c,x:b]=(out[y:c,x:b]*(1-a[:,:,None])+color*a[:,:,None]).astype(np.uint8)
    assert not np.any(out[~allowed]!=native[~allowed]),'Pixels changed outside localized text masks'
    return out,allowed,records

def render(recipe,options,dest,source):
    spec=json.loads(Path(recipe).read_text());source=Path(source);dest=Path(dest);dest.parent.mkdir(parents=True,exist_ok=True)
    assert set(options)<=set(spec['demoOptions']),'Unknown text slot'
    dec=sp.Popen(['ffmpeg','-v','error','-threads','2','-i',str(source/spec['reference']),'-an','-f','rawvideo','-pix_fmt','rgb24','-'],stdout=sp.PIPE)
    enc=sp.Popen(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s','1280x720','-r','30','-i','pipe:0','-i',str(source/spec['audio']),'-map','0:v','-map','1:a','-frames:v',str(spec['frames']),'-c:v','libx264','-threads','2','-preset','fast','-crf','16','-pix_fmt','yuv420p','-c:a','copy','-movflags','+faststart',str(dest)],stdin=sp.PIPE)
    record=[];edited=0
    for f in range(spec['frames']):
        raw=dec.stdout.read(1280*720*3);assert len(raw)==1280*720*3
        native=np.frombuffer(raw,np.uint8).reshape(720,1280,3)
        if any(a<=f<b for a,b in spec.get('blackRanges',[])):out=native;rows=[]
        else:out,mask,rows=frame(native,spec['tracks'],options,f)
        if rows:edited+=1;record.append({'frame':f,'tracks':rows})
        enc.stdin.write(out.tobytes())
    enc.stdin.close();dec.stdout.close();assert enc.wait()==0 and dec.wait()==0
    Path(str(dest)+'.runtime.json').write_text(json.dumps({'id':spec['id'],'frames':spec['frames'],'editedFrames':edited,'outsideTextMasksPreEncodeExact':True,'motionType':'fixed native motion, replaceable text','samples':record},ensure_ascii=False))
    print(spec['id'],edited,'localized frames',flush=True)

if __name__=='__main__':render(sys.argv[1],json.loads(Path(sys.argv[2]).read_text()),sys.argv[3],sys.argv[4])
