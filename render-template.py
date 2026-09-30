"""Assistant-facing native-timeline template renderer (Pillow + FFmpeg).
Usage: python3 render-template.py ML-001.json options.json output.mp4
No user-facing controls are required. Empty options preserves native visuals.
Text slots are localized approximations, NOT recovered source project layers.
"""
from pathlib import Path
import subprocess,json,sys,hashlib
from PIL import Image,ImageDraw,ImageFont,ImageFilter
import numpy as np

def clean_patch(native,box):
    x,y,w,h=box
    a=np.asarray(native.crop((x,y,x+w,y+h)),dtype=np.float32)
    # Coons surface: interpolate all four actual borders, matching their colors
    # exactly instead of copying unrelated cloud texture and leaving a rectangle.
    u=np.linspace(0,1,w,dtype=np.float32)[None,:,None]
    v=np.linspace(0,1,h,dtype=np.float32)[:,None,None]
    top=a[0:1];bottom=a[-1:];left=a[:,0:1];right=a[:,-1:]
    corners=(1-v)*((1-u)*a[0,0]+u*a[0,-1])+v*((1-u)*a[-1,0]+u*a[-1,-1])
    b=(1-v)*top+v*bottom+(1-u)*left+u*right-corners
    return Image.fromarray(np.clip(b,0,255).astype(np.uint8))

def font_path():
    paths=['/System/Library/Fonts/PingFang.ttc','/System/Library/Fonts/STHeiti Medium.ttc','/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc']
    for p in paths:
        if Path(p).exists():return p
    raise RuntimeError('Install a CJK font and add its path in font_path()')

def layer(text,p,w,h,t=None):
    size=p['size'];font=ImageFont.truetype(font_path(),size)
    lines=str(text).split('\n');pad=20
    while max(font.getlength(x) for x in lines)>w-pad*2 and size>14:
        size-=1;font=ImageFont.truetype(font_path(),size)
    tile=Image.new('RGBA',(w,h));d=ImageDraw.Draw(tile)
    lineh=round(size*1.45);base=(h-lineh*len(lines))/2
    from PIL import ImageColor
    for i,line in enumerate(lines):
        delay=p.get('lineDelays',[0]*len(lines))[i] if i<len(p.get('lineDelays',[])) else 0
        alpha=1 if t is None else max(0,min(1,(t-delay)/max(.08,p.get('fade',.2))))
        d.text((w/2,base+i*lineh),line,font=font,fill=ImageColor.getrgb(p['color'])+(round(alpha*255),),anchor='mt')
    angle=p.get('angle',0)
    if t is not None and 'rotation' in p:
        start,end=p['rotation'];progress=min(1,t/max(.01,(p['to']-p['from'])/30));angle=-(start+(end-start)*progress)
    if angle:tile=tile.rotate(angle,resample=Image.Resampling.BICUBIC)
    return tile

def render(recipe,options,destination):
    path=Path(recipe);m=json.loads(path.read_text());root=path.parent
    unknown=set(options)-set(p['key'] for p in m['slots'])
    if unknown:raise ValueError('Unknown editable slots: '+str(unknown))
    for v in options.values():
        if not isinstance(v,str) or len(v)>160:raise ValueError('Each slot requires <=160 characters')
    src=root/m['reference'];audio=root/m['audio'];out=Path(destination)
    if not options:
        subprocess.run(['ffmpeg','-v','error','-i',str(src),'-map','0','-c','copy','-movflags','+faststart','-y',str(out)],check=True)
        return {'frames':m['frames'],'mode':'native-motion-asset','noMotionRebuildClaim':True}
    W,H=m['width'],m['height'];N=m['frames'];B=W*H*3
    dec=subprocess.Popen(['ffmpeg','-v','error','-threads','2','-i',str(src),'-an','-f','rawvideo','-pix_fmt','rgb24','-'],stdout=subprocess.PIPE)
    enc=subprocess.Popen(['ffmpeg','-v','error','-threads','2','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(m['fps']),'-i','pipe:0','-i',str(audio),'-map','0:v','-map','1:a','-frames:v',str(N),'-c:v','libx264','-threads','2','-preset','veryfast','-crf','20','-pix_fmt','yuv420p','-c:a','copy','-movflags','+faststart','-y',str(out)],stdin=subprocess.PIPE)
    slots=[p for p in m['slots'] if p['key'] in options]
    tiles={p['key']:layer(options[p['key']],p,p['box'][2],p['box'][3]) for p in slots}
    protected=set(f for a,b in m['blackRanges'] for f in range(a,b))
    changed=0; black_preserved=0
    for f in range(N):
        data=dec.stdout.read(B)
        if len(data)!=B:raise RuntimeError(f'Unexpected EOF at frame {f}')
        active=[p for p in slots if p['from']<=f<p['to'] and f not in protected]
        if active:
            frame=Image.frombytes('RGB',(W,H),data)
            native=frame.copy()
            for p in active:
                x,y,w,h=p['box'];fill=p['fill']
                if fill.startswith('#'):bg=Image.new('RGB',(w,h),fill)
                else:
                    # Copy a clean moving region from THIS frame. This is explicitly
                    # a localized background approximation, not exact restoration.
                    bg=clean_patch(native,p['box'])
                tile=layer(options[p['key']],p,w,h,(f-p['from'])/m['fps']) if p.get('lineDelays') or p.get('rotation') else tiles[p['key']]
                fade=p.get('fade',0);a=min(1,(f-p['from']+1)/(max(.001,fade)*m['fps'])) if fade else 1
                if len(str(options[p['key']]).split('\n'))>1:
                    # Progressive line reveal keeps content grouped, with predictable timing.
                    pass
                if a<1:tile=tile.copy();tile.putalpha(tile.getchannel('A').point(lambda v:round(v*a)))
                bg.paste(tile,(0,0),tile)
                frame.paste(bg,(x,y))
            data=frame.tobytes();changed+=1
        if f in protected:black_preserved+=1
        enc.stdin.write(data)
    enc.stdin.close();assert enc.wait()==0;assert dec.wait()==0
    return {'frames':N,'mode':'editable-text-hybrid','patchedFrames':changed,'protectedBlackFrames':black_preserved,'unmodifiedPixelsOutsideSlots':'unchanged before H.264 encode','fidelity':'native layer + approximate local content replacement; not frame-exact reconstruction'}

if __name__=='__main__':
    recipe,config,out=sys.argv[1:4]
    result=render(recipe,json.loads(Path(config).read_text()),out)
    Path(out+'.runtime.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps(result,ensure_ascii=False))
