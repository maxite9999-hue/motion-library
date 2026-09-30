"""Fixed native motion + localized, replaceable text. Not vector reconstruction.
Usage: python3 render-faithful.py recipe.json options.json output.mp4 source_dir
Requires Pillow, numpy, opencv-python and ffmpeg. No generated extra headings.
"""
from pathlib import Path
import sys,json,subprocess as sp,functools,base64,io,zlib
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
def glyph(s,w,h,weight,shown=None,only=None):
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
    if only is not None:
        im=Image.new('L',im.size);d=ImageDraw.Draw(im)
        for j,(x,c) in enumerate(positions):
            if only[0]<=j<only[1] and (shown is None or j<shown):d.text((x,2-b[1]),c,font=f,fill=255)
    if bounds:im=im.crop(bounds)
    return np.asarray(im.resize((max(1,w),max(1,h)),Image.Resampling.LANCZOS))

def affine_layer(plane, mat, tr, f):
    result=cv2.warpAffine(plane,mat,(1280,720))
    shifts=tr.get('rowShifts',{}).get(str(f))
    if shifts is not None:
        yy,xx=np.indices((720,1280),dtype=np.float32)
        result=cv2.remap(result,(xx-np.array(shifts,np.float32)[:,None])%1280,yy,cv2.INTER_LINEAR,borderMode=cv2.BORDER_WRAP)
    return result

def measure(native,tr,f):
    x0,y0,x1,y1=tr['roi'];crop=native[y0:y1,x0:x1];ch=crop[:,:,2]
    dark=tr['ink']=='dark';kernel=cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(41,41))
    if tr['ink'] in ('red','green','gold'):
        rgb=crop.astype(float);r,g,b=rgb[:,:,0],rgb[:,:,1],rgb[:,:,2]
        if tr['ink']=='red':
            hsv=cv2.cvtColor(crop,cv2.COLOR_RGB2HSV);mask=((hsv[:,:,0]<12)|(hsv[:,:,0]>168))&(hsv[:,:,1]>45)&(r>45)&(b>=g*.55)&(r>g*1.25)
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
    colors=crop[good>0];color=np.percentile(colors,tr.get('colorPercentile',35 if dark else 85),axis=0).astype(np.uint8)
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
        if k in p and k in q:v[k]=[round(x+(y-x)*a) for x,y in zip(p[k],q[k])]
    for k in ('blurY','blurX','opacity','revealFraction'):
        if k in p and k in q:v[k]=p[k]+(q[k]-p[k])*a
    return v

def text_box(tr,value,box):
    x,y,r,b=box
    if tr.get('naturalWidth'):
        ff=face(tr.get('weight','Light'));bb=ff.getbbox(value);w=min(r-x,round((b-y)*ff.getlength(value)/max(1,bb[3]-bb[1])))
        x+=round((r-x-w)*tr.get('anchor',.5));r=x+w
    return x,y,r,b

def frame(native,tracks,options,f):
    flows={t['key']:t['flowExit'] for t in tracks if t.get('flowExit')}
    flowing=[t for t in tracks if str(f) in t.get('flowExit',flows.get(t.get('flowWith'),{})).get('maps',{}) and t['start']<=f<t['end']]
    if flowing:
        rest=[t for t in tracks if t not in flowing];out,allowed,records=frame(native,rest,options,f)
        spec=flowing[0].get('flowExit',flows.get(flowing[0].get('flowWith')));base=decode_plate(spec['baseImage']);local=[{k:v for k,v in t.items() if k not in ('flowExit','flowWith')} for t in flowing]
        result,mask,rows=frame(base,local,options,spec['baseFrame'])
        if spec.get('baseMaskBox'):
            x,y,r,b=spec['baseMaskBox'];mask[y:b,x:r]=True
        uv=np.frombuffer(zlib.decompress(base64.b64decode(spec['maps'][str(f)])),np.float16).astype(np.float32).reshape(360,640,2);uv=cv2.resize(uv,(1280,720))*2
        warped=cv2.remap(result,uv[:,:,0],uv[:,:,1],cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT)
        blur_start=spec.get('blurStart',184)
        if f>blur_start:
            sigma=min(spec.get('blurMax',3),(f-blur_start)*spec.get('blurRate',.35))
            warped=cv2.GaussianBlur(warped,(1,max(3,int(sigma*6)|1)),sigmaX=.01,sigmaY=sigma) if spec.get('verticalBlur') else cv2.GaussianBlur(warped,(0,0),sigma)
        alpha=cv2.remap(mask.astype(np.float32),uv[:,:,0],uv[:,:,1],cv2.INTER_LINEAR)
        pad=spec.get('maskPad',0)+max(0,f-spec.get('padStart',f))*spec.get('padRate',0)
        if pad:alpha=cv2.dilate(alpha,np.ones((pad*2+1,pad*2+1),np.uint8))
        alpha=cv2.GaussianBlur(alpha,(0,0),spec.get('feather',3));active=alpha>1e-5
        out[active]=(out[active]*(1-alpha[active,None])+warped[active]*alpha[active,None]).astype(np.uint8);allowed|=active;records.extend(rows)
        return out,allowed,records
    moving=[t for t in tracks if str(f) in t.get('motionPoses',{}) and t['start']<=f<t['end']]
    if moving:
        rest=[t for t in tracks if t not in moving]
        out,allowed,records=frame(native,rest,options,f)
        mat=np.array(moving[0]['motionPoses'][str(f)],np.float32)
        warp=cv2.warpPerspective if mat.shape==(3,3) else cv2.warpAffine
        inv=np.linalg.inv(mat) if mat.shape==(3,3) else cv2.invertAffineTransform(mat)
        stable=warp(native,inv,(1280,720),borderMode=cv2.BORDER_REFLECT)
        local=[{k:v for k,v in t.items() if k!='motionPoses'} for t in moving]
        rendered,mask,rows=frame(stable,local,options,f)
        warped=warp(rendered,mat,(1280,720));active=warp(mask.astype(np.uint8),mat,(1280,720),flags=cv2.INTER_NEAREST)>0
        out[active]=warped[active];allowed|=active;records.extend(rows)
        assert not np.any(out[~allowed]!=native[~allowed])
        return out,allowed,records
    out=native.copy();allowed=np.zeros(native.shape[:2],bool);records=[];layers=[];foreground=np.zeros(native.shape[:2],bool)
    for track in tracks:
        if str(f) in track.get('protectPoses',{}):
            pm=cv2.warpAffine(decode_mask(track['protectMask']),np.array(track['protectPoses'][str(f)],np.float32),(1280,720));ps=int(track.get('protectDilate',3));foreground|=cv2.dilate(pm,np.ones((ps,ps),np.uint8))>40
    for track in tracks:
        guard=track.get('protectNativeInk',{}).get(str(f))
        if guard:
            x,y,r,b,threshold=guard
            foreground[y:b,x:r]|=native[y:b,x:r,0]<threshold
    affine_pads={};joint=np.zeros(native.shape[:2],np.uint8)
    for idx,track in enumerate(tracks):
        if not track['start']<=f<track['end'] or not track.get('affineMask'):continue
        mat=np.array(track['poses'][str(f)],np.float32)
        silhouette=affine_layer(decode_mask(track['affineMask']),mat,track,f)
        if track.get('cleanupContrast') or str(f) in track.get('cleanupBoxes',{}):
            bx,by,br,bb=track['canonicalBox'];band=np.zeros((720,1280),np.uint8)
            band[max(0,by-12):min(720,bb+12),max(0,bx-18):min(1280,br+18)]=255
            region=affine_layer(band,mat,track,f)>0
            extra=track.get('cleanupBoxes',{}).get(str(f))
            if extra:
                ex,ey,er,eb=extra;region[ey:eb,ex:er]=True
            contrast=cv2.morphologyEx(cv2.cvtColor(native,cv2.COLOR_RGB2GRAY),cv2.MORPH_BLACKHAT,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(81,81)))
            silhouette=np.maximum(silhouette,((contrast>track.get('cleanupThreshold',3))&region).astype(np.uint8)*255)
        if str(f) in track.get('rowShifts',{}):
            # The glitch wraps words across the screen. Clean only observed
            # dark glyph pixels, not the white question mark behind them.
            by,bb=track['canonicalBox'][1],track['canonicalBox'][3]
            band=np.zeros((720,1280),bool);band[max(0,by-8):min(720,bb+8)]=True
            silhouette=((native[:,:,0]<210)&(native[:,:,1]<175)&band).astype(np.uint8)*255
            pad=cv2.dilate(silhouette,np.ones((5,5),np.uint8))
        else:
            mp=track.get('affinePad',9);pad=cv2.dilate(silhouette,np.ones((mp,mp),np.uint8))
        if track.get('affineClipBox'):
            x,y,r,b=track['affineClipBox'];keep=np.zeros((720,1280),np.uint8);keep[y:b,x:r]=1;pad*=keep
        floor=track.get('preserveDarkBefore',{})
        if f<floor.get('end',0):pad[native[:,:,0]<floor['threshold']]=0
        affine_pads[id(track)]=pad;joint=np.maximum(joint,pad)
    joint_clean=cv2.inpaint(native,joint,9,cv2.INPAINT_TELEA) if np.any(joint) else native
    for track in tracks:
        spec=track.get('cleanupPlate',{})
        if np.any(joint) and str(f) in spec.get('maps',{}):
            uv=np.frombuffer(zlib.decompress(base64.b64decode(spec['maps'][str(f)])),np.float16).astype(np.float32).reshape(spec.get('mapHeight',360),spec.get('mapWidth',640),2);uv=cv2.resize(uv,(1280,720))*2
            plate=cv2.remap(decode_plate(spec['baseImage']),uv[:,:,0],uv[:,:,1],cv2.INTER_LINEAR,borderMode=cv2.BORDER_REFLECT)
            if spec.get('matchTone'):
                valid=joint==0;valid[:80]=False;valid[510:]=False;valid[:,:220]=False;valid[:,900:]=False
                for c in range(3):
                    v=plate[:,:,c].astype(float);target=native[:,:,c].astype(float);sel=valid.copy()
                    for _ in range(3):
                        coef=np.linalg.lstsq(np.column_stack([v[sel],np.ones(sel.sum())]),target[sel],rcond=None)[0]
                        residual=np.abs(v*coef[0]+coef[1]-target);sel=valid&(residual<np.percentile(residual[valid],65))
                    plate[:,:,c]=np.clip(v*coef[0]+coef[1],0,255)
            # Restore only the original glyph footprint, not a rectangular
            # replacement of the surrounding moving scene.
            joint_clean[joint>0]=plate[joint>0]
            break
    for tr in tracks:
        if not tr['start']<=f<tr['end']:continue
        if 'ocrRows' in tr:
            for box in tr['ocrRows'].get(str(f),[]):
                x,y,r,b=map(int,box);x=max(0,x-2);y=max(0,y-1);r=min(1280,r+2);b=min(720,b+1)
                if r<=x or b<=y:continue
                crop=native[y:b,x:r];gray=cv2.cvtColor(crop,cv2.COLOR_RGB2GRAY)
                baseline=np.percentile(gray,90);mask=((baseline-gray.astype(float)>max(3,(baseline-50)*.1))&(gray<baseline-3)).astype(np.uint8)*255
                if np.count_nonzero(mask)<3:continue
                yy,xx=np.where(mask);pad=cv2.dilate(mask,np.ones((3,3),np.uint8));clean=cv2.inpaint(crop,pad,3,cv2.INPAINT_TELEA)
                out[y:b,x:r][pad>0]=clean[pad>0];allowed[y:b,x:r]|=pad>0
                h=max(2,round((b-y-2)*.78));value=options.get(tr['key'],tr['text']);ff=face(tr.get('weight','Light'));fb=ff.getbbox(value);w=min(r-x-4,round(h*ff.getlength(value)/max(1,fb[3]-fb[1])))
                gx=x+2;gy=y+max(0,(b-y-h)//2);a=glyph(value,w,h,tr.get('weight','Light')).astype(float)/255;color=np.percentile(crop[mask>0],25,axis=0)
                layers.append((gx,gy,gx+w,gy+h,a,color));allowed[gy:gy+h,gx:gx+w]|=a>0;records.append({'key':tr['key'],'box':[gx,gy,gx+w,gy+h]})
            continue
        tr=keyed(tr,f)
        clip_right=tr.get('clipRightByFrame',{}).get(str(f),1280)
        if clip_right<1280 and 'roi' in tr:
            tr=dict(tr,roi=tr['roi'].copy());tr['roi'][2]=min(tr['roi'][2],clip_right)
            if tr['roi'][2]<=tr['roi'][0]:continue
        frame_opacity=tr.get('frameOpacity',{}).get(str(f),1)
        if frame_opacity<=0:continue
        if tr.get('preserveClockHand'):
            # Identify the lower hand outside the word, then preserve only
            # native hand pixels through the word's replacement region.
            ink=((native[:,:,0]<100)&(native[:,:,1]<100)).astype(np.uint8)*255
            search=np.zeros_like(ink);search[520:610,350:850]=ink[520:610,350:850]
            lines=cv2.HoughLinesP(search,1,np.pi/360,15,minLineLength=35,maxLineGap=6)
            if lines is not None:
                cx,cy=600,338
                for (lx,ly,rx,ry), in lines:
                    dx,dy=rx-lx,ry-ly;length=np.hypot(dx,dy)
                    distance=abs(dy*(cx-lx)-dx*(cy-ly))/max(1,length)
                    if distance>16:continue
                    direction=np.array([dx,dy],float)/length
                    if direction[1]<0:direction=-direction
                    hand=np.zeros_like(ink);tip=np.array([cx,cy])+direction*280
                    cv2.line(hand,(cx,cy),tuple(tip.astype(int)),255,17)
                    x0,y0,x1,y1=tr['roi'];region=np.zeros_like(ink);region[y0:y1,x0:x1]=255
                    foreground|=(hand>0)&(region>0)&(ink>0)
        if tr.get('mode')=='source-button':
            pose=tr['buttonPoses'].get(str(f))
            if not pose:continue
            x,y,r,b=pose['box'];body=native[y:b,x:r].astype(float)
            hand=np.zeros((720,1280),np.uint8);hand[570:720,505:775]=decode_mask(pose['cursor'])
            cleanmask=np.zeros((720,1280),bool);cleanmask[y+3:b-3,x+3:r-3]=True;cleanmask&=hand==0
            if f>=178:
                # During the logo sweep, the leftmost source glyph survives
                # outside the shrinking white-card detector. Preserve colored
                # logo pixels, but clear neutral letter fragments beneath it.
                strip=np.zeros_like(cleanmask);strip[y+3:b-3,max(530,x-30):x+3]=True
                neutral=(native.max(2).astype(int)-native.min(2).astype(int)<35)&(native.min(2)>90)
                cleanmask|=strip&neutral
            bg=np.array([255,0,0] if f<33 else [244,244,244]);out[cleanmask]=bg;allowed|=cleanmask
            if f==179:
                remnant=np.zeros((720,1280),np.uint8);remnant[616:647,675:696]=255
                out=cv2.inpaint(out,remnant,7,cv2.INPAINT_TELEA);allowed|=remnant>0
            rows=[(tr['key'],tr['text'],[245,245,245],0)] if f<30 else [(tr['secondKey'],tr['secondText'],[90,90,90],0)]
            if f in [30,31]:rows=[(tr['key'],tr['text'],[245,245,245],(f-29)*20),(tr['secondKey'],tr['secondText'],[90,90,90],(f-32)*20)]
            for key,default,col,dy in rows:
                value=options.get(key,default);h=28;w=round(h*len(value)*1.05);px=round(((1280 if f>=8 else x+r)-w)/2);py=round(((1261 if f>=8 else y+b)-h)/2)+dy
                if f<7:px+=round((7-f)**2*3.5)
                alpha=np.zeros((720,1280),np.float32);alpha[max(0,py):py+h,max(0,px):px+w]=glyph(value,w,h,'Medium')/255
                if f<7:alpha=cv2.GaussianBlur(alpha,(0,0),max(.1,(7-f)*1.1),sigmaY=.6)
                clip=np.zeros((720,1280),bool);clip[y+3:b-3,x+3:r-3]=True;alpha*=clip&(hand==0)
                layers.append((0,0,1280,720,alpha,np.array(col)));allowed|=alpha>0
                records.append({'key':key,'box':[px,py,px+w,py+h],'sourceButton':[x,y,r,b],'cursorPreserved':True})
            continue
        if tr.get('affineMask'):
            mat=np.array(tr['poses'][str(f)],np.float32)
            silhouette=affine_layer(decode_mask(tr['affineMask']),mat,tr,f)
            if tr.get('adaptiveCleanup'):
                bx,by,br,bb=tr['canonicalBox'];region=np.zeros((720,1280),np.uint8);region[max(0,by-5):min(720,bb+5),max(0,bx-12):min(1280,br+12)]=255
                region=cv2.warpAffine(region,mat,(1280,720))>0
                fg=(native[:,:,0]<210)&(native[:,:,1]<190)&region
                silhouette=np.maximum(silhouette,fg.astype(np.uint8)*255)
            opacity_silhouette=silhouette.copy()
            if tr.get('cleanupContrast'):
                bx,by,br,bb=tr['canonicalBox'];band=np.zeros((720,1280),np.uint8)
                band[max(0,by-22):min(720,bb+22),max(0,bx-30):min(1280,br+30)]=255
                dm=np.array(tr.get('drawPoses',{}).get(str(f),mat),np.float32)
                region=(cv2.warpAffine(band,mat,(1280,720))>0)|(cv2.warpAffine(band,dm,(1280,720))>0)
                contrast=cv2.morphologyEx(cv2.cvtColor(native,cv2.COLOR_RGB2GRAY),cv2.MORPH_BLACKHAT,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(81,81)))
                # Faint entering English is still a local dark stroke even when
                # it is much lighter than the old fixed RGB threshold.
                fg=(contrast>tr.get('cleanupThreshold',2))&region
                silhouette=np.maximum(silhouette,fg.astype(np.uint8)*255)
            pad=cv2.dilate(silhouette,np.ones((9,9),np.uint8))
            if id(tr) in affine_pads:pad=affine_pads[id(tr)]
            ys,xs=np.where(pad)
            if not len(xs):continue
            x0=max(0,int(xs.min())-12);y0=max(0,int(ys.min())-12);x1=min(1280,int(xs.max())+13);y1=min(720,int(ys.max())+13)
            crop=native[y0:y1,x0:x1];pm=pad[y0:y1,x0:x1]
            # Clean overlapping source lines together: a later line must never
            # paint previously removed English back into a neighboring region.
            if id(tr) in affine_pads:
                pm=affine_pads[id(tr)][y0:y1,x0:x1]
            clean=joint_clean[y0:y1,x0:x1]
            core=cv2.erode(opacity_silhouette[y0:y1,x0:x1],np.ones((3,3),np.uint8))>180
            if not np.any(core):continue
            contrast=clean.astype(float).mean(2)-crop.astype(float).mean(2)
            opacity=float(np.clip(np.percentile(contrast[core],tr.get('opacityPercentile',70))/max(1,np.median(clean[core])-25),0,1))
            region=out[y0:y1,x0:x1];region[pm>0]=clean[pm>0];allowed[y0:y1,x0:x1]|=pm>0
            x,y,r,b=tr['canonicalBox'];val=options.get(tr['key'],tr['text']);h=b-y;w=r-x
            if tr.get('naturalWidth'):
                ff=face(tr.get('weight','Light'));bb=ff.getbbox(val);w=min(w,round(h*ff.getlength(val)/max(1,bb[3]-bb[1])))
                x+=round((r-x-w)*tr.get('affineAnchor',0))
            fraction=tr.get('drawReveals',{}).get(str(f),1);shown=max(1,int(len(val)*fraction)) if fraction<.99 else None
            plane=np.zeros((720,1280),np.uint8);plane[y:b,x:x+w]=glyph(val,w,h,tr.get('weight','Light'),shown)
            for span in tr.get('weightSpans',[]):
                lo,hi=span['range'];old=glyph(val,w,h,tr.get('weight','Light'),shown,only=(lo,hi));new=glyph(val,w,h,span['weight'],shown,only=(lo,hi))
                plane[y:b,x:x+w]=np.maximum(np.clip(plane[y:b,x:x+w].astype(int)-old,0,255).astype(np.uint8),new)
            # Keep cleanup tied to the measured native glyph, but display text
            # on a temporally coherent, source-derived trajectory when supplied.
            drawmat=np.array(tr.get('drawPoses',{}).get(str(f),mat),np.float32)
            opacity=tr.get('drawOpacities',{}).get(str(f),opacity)
            a=affine_layer(plane,drawmat,tr,f).astype(float)/255*opacity
            if tr.get('drawBlur',{}).get(str(f),0)>.1:a=cv2.GaussianBlur(a,(0,0),tr['drawBlur'][str(f)])
            if str(f) in tr.get('drawVerticalBlur',{}):
                sigma=tr['drawVerticalBlur'][str(f)];a=cv2.GaussianBlur(a,(1,max(3,int(sigma*6)|1)),sigmaX=.01,sigmaY=sigma)
            if tr.get('affineClipBox'):
                x,y,r,b=tr['affineClipBox'];keep=np.zeros((720,1280),np.uint8);keep[y:b,x:r]=1;a*=keep
            floor=tr.get('preserveDarkBefore',{})
            if f<floor.get('end',0):a[native[:,:,0]<floor['threshold']]=0
            layers.append((0,0,1280,720,a,np.array(tr.get('color',[25,25,24]))));allowed|=a>0
            records.append({'key':tr['key'],'affine':drawmat.tolist(),'cleanupAffine':mat.tolist(),'opacity':opacity});continue
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
            if tr.get('cleanPlate'):
                clean=crop.copy();plate=decode_plate(tr['cleanPlate']);clean[pad>0]=plate[pad>0]
            # A source-derived silhouette also catches the faint first/last glyphs.
            # Estimate contrast on its eroded interior, not on moving background.
            core=cv2.erode(mask,np.ones((3,3),np.uint8))>0
            if not np.any(core):core=mask>0
            delta=crop.astype(float)-clean.astype(float)
            signal=delta[core].mean(1);strength=np.percentile(np.abs(signal) if tr.get('absoluteContrast') else signal,75)
            opacity=float(np.clip(strength/max(1,tr.get('fullContrast',180)),0,1))
            out[y0:y1,x0:x1]=clean;allowed[y0:y1,x0:x1]|=pad>0
            val=options.get(tr['key'],tr['text']);x,y,r,b=text_box(tr,val,tr['lockedBox']);a=glyph(val,r-x,b-y,tr.get('weight','Light')).astype(float)/255*opacity
            color=np.array(tr.get('color',[245,245,240]))
            if tr.get('sourceGradient'):
                # Sample actual source ink along the text, including its lighting
                # gradient. Never replace a metallic source fill by one flat RGB.
                columns=[];values=[]
                for left in range(0,crop.shape[1],16):
                    stop=min(crop.shape[1],left+16);sel=core[:,left:stop]
                    if np.count_nonzero(sel)>3:
                        columns.append(left+(stop-left)/2)
                        values.append(np.percentile(crop[:,left:stop][sel],65,axis=0))
                if len(columns)>1:
                    grid=np.linspace(tr['lockedBox'][0]-x0,tr['lockedBox'][2]-x0,r-x)
                    ramp=np.stack([np.interp(grid,columns,np.array(values)[:,c]) for c in range(3)],axis=-1)
                    color=np.broadcast_to(ramp[None,:,:],(b-y,r-x,3));a=glyph(val,r-x,b-y,tr.get('weight','Light')).astype(float)/255*min(1,opacity*4)
            layers.append((x,y,r,b,a,color));allowed[y:b,x:r]|=a>0
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
            if tr.get('gradientMask'):
                core=cv2.erode(decode_mask(tr['gradientMask']),np.ones((3,3),np.uint8))>0
                columns=[];values=[]
                for left in range(0,crop.shape[1],16):
                    stop=min(crop.shape[1],left+16);sel=core[:,left:stop]
                    if np.count_nonzero(sel)>3:
                        columns.append((left+stop)/2);values.append(np.percentile(crop[:,left:stop][sel],65,axis=0))
                if len(columns)>1:
                    grid=np.linspace(tr['lockedBox'][0]-x0,tr['lockedBox'][2]-x0,r-x)
                    ramp=np.stack([np.interp(grid,columns,np.array(values)[:,ch]) for ch in range(3)],axis=-1)
                    color=np.broadcast_to(ramp[None,:,:],(b-y,r-x,3))
                    # Fades are already present in the sampled ink color.
                    contrast=float(np.percentile(np.abs(crop-plate)[core],90))
                    a=glyph(val,r-x,b-y,tr.get('weight','Light'),shown).astype(np.float32)/255*np.clip(contrast/25,0,1)
            a*=frame_opacity
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
        x0,y0,x1,y1=tr['roi'];mp=tr.get('maskPad',11)
        my=max(mp,round(tr.get('blurY',0)*4)) if tr.get('clearBlurEnvelope') else mp
        pad=cv2.dilate(mask,np.ones((my,mp),np.uint8))
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
            rh*=tr.get('drawHeightScale',1)
            rw=max(2,round(rw));rh=max(2,round(rh));value=options.get(tr['key'],tr['text'])
            if tr.get('naturalWidth'):
                ff=face(tr.get('weight','Medium'));bb=ff.getbbox(value);nw=min(rw,round(rh*ff.getlength(value)/max(1,bb[3]-bb[1])));shift=(rw-nw)*(.5-tr.get('anchor',.5));rad=np.deg2rad(theta);center=(center[0]-shift*np.cos(rad),center[1]-shift*np.sin(rad));rw=nw
            a=glyph(value,rw,rh,tr.get('weight','Medium'))
            rad=np.deg2rad(theta);u=np.array([np.cos(rad),np.sin(rad)]);v=np.array([-np.sin(rad),np.cos(rad)]);c=np.array(center)
            dst=np.float32([c-u*rw/2-v*rh/2,c+u*rw/2-v*rh/2,c-u*rw/2+v*rh/2]);mat=cv2.getAffineTransform(np.float32([[0,0],[rw,0],[0,rh]]),dst)
            a=cv2.warpAffine(a,mat,(1280,720),flags=cv2.INTER_LINEAR).astype(float)/255
            if tr.get('sourceGradient'):
                projection=(pts-np.array(center))@u;colors=native[(yy+y0),(xx+x0)]
                columns=[];values=[]
                for left in np.linspace(projection.min(),projection.max(),20)[:-1]:
                    sel=(projection>=left)&(projection<left+(projection.max()-projection.min())/19)
                    if np.count_nonzero(sel)>8:columns.append(left);values.append(np.percentile(colors[sel],55,axis=0))
                if len(columns)>1:
                    gy,gx=np.mgrid[0:720,0:1280];grid=(gx-center[0])*u[0]+(gy-center[1])*u[1]
                    color=np.stack([np.interp(grid,columns,np.array(values)[:,ch]) for ch in range(3)],axis=-1)
            layers.append((0,0,1280,720,a,color));allowed|=a>0
            records.append({'key':tr['key'],'angle':float(theta),'size':[rw,rh],'center':list(center)});continue
        box=np.array(box,dtype=int);angle=tr.get('angle',0);reveal=1.
        if 'fullBox' in tr and f<tr.get('revealEnd',tr['start']):
            target=np.array(tr['fullBox'])
            reveal=np.clip((target[3]-box[1])/max(1,target[3]-target[1]) if angle else (box[2]-target[0])/max(1,target[2]-target[0]),0,1);box=target
        elif 'lockedBox' in tr:box=np.array(tr['lockedBox'])
        if tr.get('naturalWidth') and not angle:box=np.array(text_box(tr,options.get(tr['key'],tr['text']),box))
        elif tr.get('naturalWidth') and angle:
            val=options.get(tr['key'],tr['text']);ff=face(tr.get('weight','Medium'));bb=ff.getbbox(val)
            span=min(box[3]-box[1],round((box[2]-box[0])*ff.getlength(val)/max(1,bb[3]-bb[1])))
            box[1]+=round((box[3]-box[1]-span)*tr.get('anchor',.5));box[3]=box[1]+span
        x,y,r,b=box;w,h=r-x,b-y
        if w<2 or h<2:continue
        value=options.get(tr['key'],tr['text'])
        if 'revealFraction' in tr:reveal=tr['revealFraction']
        shown=max(1,int(len(value)*reveal)) if reveal<.99 else None
        a=glyph(value,h if angle else w,w if angle else h,tr.get('weight','Light'),shown)
        if angle:a=np.rot90(a,-1 if angle<0 else 1)
        tile=np.broadcast_to(color,(h,w,3)).copy()
        xa=max(0,x);ya=max(0,y);xb=min(1280,r,clip_right);yb=min(720,b)
        if xb<=xa:continue
        alpha=a[ya-y:yb-y,xa-x:xb-x].astype(np.float32)/255
        if alpha.size:
            if max(tr.get('blurY',0),tr.get('blurX',0))>.1:
                plane=np.zeros((720,1280),np.float32);plane[ya:yb,xa:xb]=alpha;sx=tr.get('blurX',.01);sy=tr.get('blurY',.01)
                kx=max(3,int(sx*6)|1) if sx>.1 else 1;ky=max(3,int(sy*6)|1) if sy>.1 else 1
                plane=cv2.GaussianBlur(plane,(kx,ky),sigmaX=max(.01,sx),sigmaY=max(.01,sy),borderType=cv2.BORDER_CONSTANT)
                layers.append((0,0,1280,720,plane,color));allowed|=plane>0
            else:
                layers.append((xa,ya,xb,yb,alpha,color))
                allowed[ya:yb,xa:xb]|=alpha>0
            if not angle:
                for span in tr.get('colorSpans',[]):
                    j=value.find(span['text'])
                    if j>=0:
                        ha=glyph(value,w,h,tr.get('weight','Light'),shown,(j,j+len(span['text'])))[ya-y:yb-y,xa-x:xb-x].astype(np.float32)/255
                        layers.append((xa,ya,xb,yb,ha,np.array(span['color'])));allowed[ya:yb,xa:xb]|=ha>0
        records.append({'key':tr['key'],'box':box.tolist(),'reveal':float(reveal)})
    for x,y,b,c,a,color in layers:
        out[y:c,x:b]=(out[y:c,x:b]*(1-a[:,:,None])+color*a[:,:,None]).astype(np.uint8)
    out[foreground]=native[foreground]
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
