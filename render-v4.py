# -*- coding: utf-8 -*-
"""Reusable Chinese motion compositions. PIL + numpy + FFmpeg, no network.
python3 render-v4.py recipe.json options.json result.mp4 [source-directory]
This is a semantic visual rebuild, not a pixel-exact reconstruction.
"""
from pathlib import Path
import json,sys,subprocess,math,functools
import numpy as np
from PIL import Image,ImageDraw,ImageFont,ImageFilter,ImageOps

def ease(x):return 1-(1-max(0,min(1,x)))**3
FONT=next((str(p) for p in [Path('/System/Library/Fonts/STHeiti Medium.ttc'),Path('/System/Library/Fonts/PingFang.ttc'),Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')] if p.exists()),None)
if not FONT:raise RuntimeError('A CJK font is required')
@functools.lru_cache(200)
def font(size):return ImageFont.truetype(FONT,max(12,round(size)))
def text(im,s,xy,size=54,color='#171715',width=1120,align='center',alpha=1):
    s=str(s);fs=size
    while font(fs).getlength(s)>width and fs>12:fs-=1
    f=font(fs);b=f.getbbox(s);x,y=xy
    if align=='center':x-=f.getlength(s)/2
    y-=(b[1]+b[3])/2
    tile=Image.new('RGBA',im.size);ImageDraw.Draw(tile).text((x,y),s,font=f,fill=color)
    if alpha<1:tile.putalpha(tile.getchannel('A').point(lambda v:round(v*max(0,alpha))))
    im.paste(tile,(0,0),tile)
def wrap(s,count=25):
    return [s[i:i+count] for i in range(0,len(s),count)] or ['']
def round_paste(im,content,box,radius=16):
    x,y,w,h=map(round,box);w=max(1,w);h=max(1,h)
    pic=ImageOps.fit(content,(w,h));mask=Image.new('L',(w,h));ImageDraw.Draw(mask).rounded_rectangle((0,0,w,h),radius=radius,fill=255)
    im.paste(pic,(x,y),mask)

class Renderer:
    def __init__(self,recipe,options):
        self.path=Path(recipe);self.root=self.path.parent;self.m=json.loads(self.path.read_text());self.options=options
        media_keys={'asset','footage'}|{f'person{i+1}Asset' for i in range(6)}
        allowed=set(self.m['demoOptions'])|media_keys
        if set(options)-allowed:raise ValueError('Unknown options: '+str(set(options)-allowed))
        if any(not isinstance(v,str) or len(v)>220 for k,v in options.items() if k not in media_keys):raise ValueError('Text inputs must be strings of up to 220 characters')
        ar=self.root/self.m.get('assetRoot','assets');self.assets={p.stem:Image.open(p).convert('RGB') for p in ar.glob('*.png')}
        if 'asset' in options:self.assets['custom']=Image.open(options['asset']).convert('RGB')
        for i in range(6):
            if f'person{i+1}Asset' in options:self.assets[f'person-{i}']=Image.open(options[f'person{i+1}Asset']).convert('RGB')
    def bg(self,f,dark=False,name='gold'):
        img=self.assets.get('custom',self.assets.get(name,self.assets['gold']))
        # A small deliberate camera move keeps the rebuilt clean plate alive.
        zoom=1.025+.012*math.sin(f/120);w=round(1280*zoom);h=round(720*zoom)
        im=ImageOps.fit(img,(w,h)).crop(((w-1280)//2,(h-720)//2,(w+1280)//2,(h+720)//2))
        if dark:im=Image.blend(im,Image.new('RGB',im.size,'#0b1016'),.64)
        return im
    def lines(self,s):return [self.options.get(k,v) for k,v in zip(s['keys'],s['texts'])]
    def person(self,s,phase,index=None,people=None):
        t=phase;im=self.bg(round(t*30));idx=s.get('person',0) if index is None else index
        vals=self.lines(s) if people is None else people[idx]
        pic=self.assets.get(f'person-{idx}',self.assets['gold'])
        enter=ease(t/.35);x=660+(1-enter)*220
        # Original portrait materials are reused; only labels and card geometry
        # are parametric. Labels do not bake over the original portrait.
        round_paste(im,pic,(x,35,560,650),10)
        text(im,vals[0],(45,110),55,align='left',width=590,alpha=enter)
        text(im,vals[1],(45,180),26,align='left',width=570,alpha=enter)
        text(im,'净资产',(45,315),27,align='left',alpha=enter)
        text(im,vals[2],(45,382),57,align='left',width=570,alpha=ease((t-.15)/.3))
        if t>.55:
            label=vals[3] if len(vals)>3 else '白手起家';tile=Image.new('RGBA',(1000,240))
            text(tile,label,(500,120),112,'#a51119',width=930)
            scale=1+.45*(1-ease((t-.55)/.15));tile=tile.resize((round(1000*scale),round(240*scale))).rotate(23,Image.Resampling.BICUBIC,expand=True)
            im.paste(tile,(round(640-tile.width/2),round(440-tile.height/2)),tile)
        return im
    def draw(self,s,f,native):
        t=(f-s['start'])/30+s.get('motionOffset',0);duration=(s['end']-s['start'])/30;u=t/max(.001,duration);kind=s['kind'];lines=self.lines(s)
        if kind=='flash':return Image.new('RGB',(1280,720),'white')
        if kind=='person':return self.person(s,t)
        if kind in ['people','collage']:
            people=[[self.options.get(k,v) for k,v in zip(ks,vs)] for ks,vs in zip(s['peopleKeys'],s['people'])]
            if kind=='people':
                index=min(5,int(u*6));local=t-index*duration/6
                people=[row+[lines[0]] for row in people]
                im=self.person(s,local,index,people)
                if local<.1 and index:
                    im=im.filter(ImageFilter.GaussianBlur(10*(1-local/.1)))
                return im
            im=self.bg(f)
            for j in range(6):
                col=j%3;row=j//3;progress=ease((t-j*.05)/.3)
                w=290*progress;h=240*progress
                round_paste(im,self.assets[f'person-{j}'],(175+col*330+(290-w)/2,50+row*285+(240-h)/2,w,h))
            if lines:text(im,lines[0],(640,673),38,width=1100,alpha=ease((t-.2)/.3))
            return im
        if kind=='split':
            im=Image.new('RGB',(1280,720),'#253337');im.paste(native.crop((0,0,640,720)),(0,0))
            # Feather the edge of the native left half; no opaque caption panel.
            overlay=Image.new('RGB',(150,720),'#253337');mask=Image.linear_gradient('L').rotate(90).resize((150,720));im.paste(overlay,(515,0),mask)
            for j,line in enumerate(lines):text(im,line,(945,180+j*175+30*(1-ease((t-j*.65)/.4))),91,'#e4b442' if j==2 else '#f0efea',width=540,alpha=ease((t-j*.65)/.3))
            return im
        if kind in ['cinema','question','stamp','notice']:
            im=self.bg(f,True,s.get('background','city'))
            if kind=='stamp':
                tile=Image.new('RGBA',(1150,260));color='#cc303b' if s.get('tone')=='red' else '#59c667'
                text(tile,lines[0],(575,130),109,color,width=1080)
                p=ease(t/.18);tile=tile.resize((round(1150*(1.4-.4*p)),round(260*(1.4-.4*p)))).rotate(16,Image.Resampling.BICUBIC,expand=True)
                im.paste(tile,(round(640-tile.width/2),round(360-tile.height/2)),tile);return im
            if kind=='notice':
                text(im,lines[0],(640,130),60,'#faf8f0',alpha=ease(t/.4))
                for j,line in enumerate(lines[1:]):text(im,line,(640,245+j*66),31,'#f3f0e9',alpha=ease((t-.2-j*.08)/.4))
                return im
            y=[150,555,360][s.get('position',2)] if kind=='question' else 360
            for j,line in enumerate(lines):text(im,line,(640,y+j*88+24*(1-ease(t/.4))),53 if kind=='question' else 61,'white',alpha=ease(t/.4))
            return im
        if kind=='article':
            im=Image.new('RGB',(1280,720),'#f2eee8');d=ImageDraw.Draw(im)
            scroll=max(0,(t+s.get('offset',0)-1.6))*25
            zoom=1 if t<3.6 else 1-.28*ease((t-3.6)/.5)
            page=Image.new('RGB',(1060,1400),'#ffffff');pd=ImageDraw.Draw(page);pd.rectangle((0,0,1060,80),fill='#142f42')
            text(page,'财经观察',(45,40),31,'white',align='left');y=155
            for j,line in enumerate(lines):
                for part in wrap(line,21 if j==0 else 30):text(page,part,(58,y-scroll),42 if j==0 else 28,align='left',width=945);y+=65 if j==0 else 50
                y+=30
            pd.rectangle((0,0,1060,80),fill='#142f42');text(page,'财经观察',(45,40),31,'white',align='left')
            page=page.crop((0,0,1060,720)).resize((round(1060*zoom),round(720*zoom)))
            im.paste(page,(40,0))
            if t>3.6:
                x=790+round(160*(1-ease((t-3.6)/.5)));d=ImageDraw.Draw(im);d.rounded_rectangle((x,60,1250,650),radius=12,fill='#ffffff',outline='#d5cbbb',width=2)
                yy=125
                for line in lines[1:]:
                    for part in wrap(line,15):
                        if yy<625:text(im,part,(x+25,yy),23,align='left',width=400)
                        yy+=38
                    yy+=20
            if s.get('flash') and t<.25:im=Image.blend(Image.new('RGB',im.size,'white'),im,ease(t/.25))
            return im
        im=self.bg(f,s.get('dark',False));ink='#f4f1e9' if s.get('dark') else '#171714'
        if kind in ['title','chapter','closing']:
            if kind=='closing':im=Image.new('RGB',im.size,'#080808');ink='#eeeae2'
            for j,line in enumerate(lines):
                delay=(j*1.25 if kind=='closing' else j*.65 if kind=='chapter' else j*.35)
                progress=ease((t-delay)/.45)
                size=69 if j==s.get('strong',-1) else 54 if j==0 else 44
                y=360+(j-(len(lines)-1)/2)*110+25*(1-progress)
                text(im,line,(640,y),size,ink,alpha=progress)
            return im
        if kind=='rotating':
            tile=Image.new('RGBA',(1280,720))
            for j,line in enumerate(lines):text(tile,line,(640,225+j*142),89,alpha=ease((t-j*.45)/.25))
            angle=-14+17*ease(t/max(.3,duration*.85));tile=tile.rotate(angle,Image.Resampling.BICUBIC)
            im.paste(tile,(0,0),tile);return im
        if kind=='equation':
            text(im,lines[0],(260,355),75,alpha=ease(t/.18))
            text(im,'=',(505,355),75,alpha=ease((t-.12)/.18))
            text(im,lines[1],(850,355),57,width=620,alpha=ease((t-.3)/.4))
            if s.get('stamp') and t>1.3:
                tile=Image.new('RGBA',(900,240));text(tile,lines[2],(450,120),142,'#a51119');tile=tile.rotate(16,Image.Resampling.BICUBIC,expand=True);im.paste(tile,(round(640-tile.width/2),round(385-tile.height/2)),tile)
            return im
        if kind=='definition':
            text(im,lines[0],(640,250),92);ImageDraw.Draw(im).line((300,327,980,327),fill='#322717',width=3)
            text(im,lines[1],(640,410),39,width=1040,alpha=ease((t-.35)/.5));return im
        if kind=='metric':
            text(im,lines[0],(640,175),42,alpha=ease(t/.2));scale=.7+.3*ease(t/.4)
            text(im,lines[1],(640,360),round(112*scale),width=1160)
            if len(lines)>2:text(im,lines[2],(640,505),38,alpha=ease((t-.35)/.4))
            return im
        if kind=='wealth':
            d=ImageDraw.Draw(im);level=s.get('level',1);count=min(1000,max(1,round(level*(.2+.8*ease(t/1.5)))))
            for j in range(count):
                cols=40 if level>100 else 10;x=180+(j%cols)*(920/max(1,cols-1));y=150+(j//cols)*(15 if level>100 else 35);r=3 if level>100 else 8 if count>10 else 16;d.ellipse((x-r,y-r,x+r,y+r),fill='#423b24')
            text(im,lines[0],(640,70),42);text(im,lines[1],(640,605),82,'#fff7d9');return im
        if kind=='problem':
            text(im,lines[0],(640,145),46,alpha=ease(t/.4));text(im,lines[1],(410,345),90,alpha=ease((t-.6)/.4));text(im,lines[2],(410,465),68,alpha=ease((t-1.2)/.4),width=680)
            d=ImageDraw.Draw(im);cx=980;cy=360;r=95*ease((t-.8)/.5);d.ellipse((cx-r,cy-r,cx+r,cy+r),outline='#2a2924',width=7);text(im,'￥',(cx,cy),110,alpha=ease((t-.8)/.5));return im
        if kind=='brand':
            text(im,lines[0],(640,335),112,alpha=ease(t/.5));d=ImageDraw.Draw(im);d.arc((390,350,890,485),0,150,fill='#241f16',width=12);return im
        if kind=='network':
            d=ImageDraw.Draw(im)
            for j,label in enumerate(lines[1:]):
                p=ease((t-j*.12)/.45);angle=j*math.tau/6;x=640+450*math.cos(angle)*p;y=360+235*math.sin(angle)*p
                d.line((640,360,x,y),fill='#685330',width=2);d.rounded_rectangle((x-97,y-38,x+97,y+38),radius=14,fill='#f9efd7',outline='#806831',width=2);text(im,label,(x,y),31,alpha=p,width=180)
            d.rounded_rectangle((405,300,875,414),radius=16,fill='#f9efd7',outline='#806831',width=2)
            text(im,lines[0],(640,356),43,width=440)
            return im
        if kind=='lesson':
            stage=s.get('stage',0);pic=self.assets['lesson'];p=ease(t/.7)
            if stage<2:round_paste(im,pic,(170,70,940,520),18)
            else:
                w=940-(340 if stage>2 else 340*p);h=w*520/940;x=(1280-w)/2;y=90
                ImageDraw.Draw(im).rounded_rectangle((x-16,y-16,x+w+16,y+h+16),radius=20,fill='#25292b');round_paste(im,pic,(x,y,w,h),12);ImageDraw.Draw(im).polygon([(x-35,y+h+16),(x+w+35,y+h+16),(x+w+85,y+h+48),(x-85,y+h+48)],fill='#737a7e')
            text(im,lines[0],(640,610),54,'#236b2f' if stage==3 else '#24251d');text(im,lines[1],(640,672),31);return im
        raise ValueError('Unknown kind '+kind)
    def render(self,destination,source_root=None):
        m=self.m;root=Path(source_root) if source_root else self.root;out=Path(destination);out.parent.mkdir(parents=True,exist_ok=True)
        source=self.options.get('footage',str(root/m['reference']))
        dec=subprocess.Popen(['ffmpeg','-v','error','-threads','2',*(['-stream_loop','-1'] if 'footage' in self.options else []),'-i',source,'-vf','scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,fps=30','-frames:v',str(m['frames']),'-an','-f','rawvideo','-pix_fmt','rgb24','-'],stdout=subprocess.PIPE)
        enc=subprocess.Popen(['ffmpeg','-v','error','-f','rawvideo','-pix_fmt','rgb24','-s','1280x720','-r','30','-i','pipe:0','-i',str(root/m['audio']),'-map','0:v','-map','1:a','-frames:v',str(m['frames']),'-c:v','libx264','-threads','2','-preset','veryfast','-crf','19','-pix_fmt','yuv420p','-c:a','copy','-movflags','+faststart','-y',str(out)],stdin=subprocess.PIPE)
        changed=0
        for f in range(m['frames']):
            raw=dec.stdout.read(1280*720*3)
            if len(raw)!=1280*720*3:raise RuntimeError('Unexpected source EOF')
            protected=any(a<=f<b for a,b in m['blackRanges']);active=next((s for s in m['scenes'] if s['start']<=f<s['end']),None)
            if active and not protected:raw=self.draw(active,f,Image.frombytes('RGB',(1280,720),raw)).convert('RGB').tobytes();changed+=1
            enc.stdin.write(raw)
        enc.stdin.close();dec.stdout.close();assert enc.wait()==0 and dec.wait()==0
        result={'id':m['id'],'frames':m['frames'],'renderedFrames':changed,'fidelity':m['fidelity'],'optionsApplied':self.options,'audio':'native AAC copy; gain unchanged'}
        Path(str(out)+'.runtime.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(m['id'],changed,'/',m['frames'],flush=True)

if __name__=='__main__':
    if len(sys.argv)<4:raise SystemExit(__doc__)
    Renderer(sys.argv[1],json.loads(Path(sys.argv[2]).read_text())).render(sys.argv[3],sys.argv[4] if len(sys.argv)>4 else None)
