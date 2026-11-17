"""Editable pixel documents, bounded history and portable .nandart projects."""
from dataclasses import asdict
from pathlib import Path
from io import BytesIO
import json
import zipfile
import tempfile
from PIL import Image, ImageDraw, ImageChops
from core import Settings

PALETTE={'Noir':(0,0,0,255),'Blanc':(255,255,255,255),'Transparent':(0,0,0,0)}


class EditDocument:
    def __init__(self,frames):
        self.frames=[im.convert('RGBA').copy() for im in frames]
        self.undo_stack=[];self.redo_stack=[];self.active=None;self.changed=False

    def begin(self,index):
        self.finish()
        self.active=(index,self.frames[index].copy())

    def line(self,index,start,end,color,size=1):
        image=self.frames[index];draw=ImageDraw.Draw(image)
        size=max(1,min(32,int(size)))
        draw.line([start,end],fill=color,width=size)
        if size>1:
            half=size//2
            for x,y in (start,end):draw.rectangle((x-half,y-half,x-half+size-1,y-half+size-1),fill=color)

    def fill(self,index,point,color):
        ImageDraw.floodfill(self.frames[index],point,color,thresh=0)

    def finish(self):
        if self.active is None:return False
        index,before=self.active;self.active=None;after=self.frames[index]
        if before.tobytes()==after.tobytes():return False
        self.undo_stack.append((index,before,after.copy()));self.redo_stack.clear();self.changed=True
        while len(self.undo_stack)>40 or (len(self.undo_stack)>1 and sum(a.width*a.height*8 for _,a,_ in self.undo_stack)>32_000_000):
            self.undo_stack.pop(0)
        return True

    def undo(self):
        self.finish()
        if not self.undo_stack:return None
        item=self.undo_stack.pop();index,before,after=item
        self.frames[index]=before.copy();self.redo_stack.append(item);self.changed=True
        return index

    def redo(self):
        if not self.redo_stack:return None
        item=self.redo_stack.pop();index,before,after=item
        self.frames[index]=after.copy();self.undo_stack.append(item);self.changed=True
        return index


def pixel_overrides(base,frames):
    result={}
    for index,(original,image) in enumerate(zip(base,frames)):
        if original.size!=image.size:raise ValueError('La taille des images retouchées doit rester identique.')
        diff=ImageChops.difference(original,image)
        r,g,b,a=diff.split();box=ImageChops.lighter(ImageChops.lighter(r,g),ImageChops.lighter(b,a)).getbbox()
        if box:
            changes={}
            for y in range(box[1],box[3]):
                for x in range(box[0],box[2]):
                    value=image.getpixel((x,y))
                    if value!=original.getpixel((x,y)):changes[(x,y)]=value
            result[index]=(image.size,changes)
    return result


def apply_overrides(frames,overrides):
    output=list(frames)
    for index,(size,changes) in overrides.items():
        if index<len(output) and output[index].size==size:
            image=output[index].copy()
            for point,value in changes.items():image.putpixel(point,value)
            output[index]=image
    return output


def save_artwork(path,frames,base,source,settings,name):
    if len(frames)!=len(base):raise ValueError('Nombre d’images incohérent.')
    def encode(image):
        stream=BytesIO();image.save(stream,format='PNG');return stream.getvalue()
    # Replace only after a complete new archive has been written.
    path=Path(path)
    with tempfile.NamedTemporaryFile(prefix=path.name+'.',suffix='.tmp',dir=path.parent,delete=False) as stream:
        temporary=Path(stream.name)
    try:
        with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('project.json',json.dumps({'format':'nandart','version':1,'class':name,
                'settings':asdict(settings),'frames':len(frames)},ensure_ascii=False))
            archive.writestr('source.png',encode(source))
            for i,(image,original) in enumerate(zip(frames,base)):
                archive.writestr(f'frames/{i:03d}.png',encode(image))
                archive.writestr(f'base/{i:03d}.png',encode(original))
        temporary.replace(path)
    finally:
        if temporary.exists():temporary.unlink()


def _load_image(data,max_pixels=512*256):
    with Image.open(BytesIO(data)) as image:
        if image.width*image.height>max_pixels:raise ValueError('Image trop grande dans le projet.')
        return image.convert('RGBA')


def load_artwork(path):
    path=Path(path)
    if path.suffix.lower()=='.nandart':
        with zipfile.ZipFile(path) as archive:
            info=archive.getinfo('project.json')
            if info.file_size>1_000_000:raise ValueError('Manifeste trop volumineux.')
            data=json.loads(archive.read(info))
            if data.get('format')!='nandart' or data.get('version')!=1:raise ValueError('Format artwork non reconnu.')
            count=data['frames']
            if not isinstance(count,int) or not 1<=count<=256:raise ValueError('Nombre d’images invalide.')
            frames=[];base=[]
            for i in range(count):
                for prefix,target in (('frames',frames),('base',base)):
                    member=archive.getinfo(f'{prefix}/{i:03d}.png')
                    if member.file_size>2_000_000:raise ValueError('Image compressée trop volumineuse.')
                    image=_load_image(archive.read(member))
                    if image.width>512 or image.height>256:raise ValueError('Dimensions hors écran Hack.')
                    target.append(image)
                if frames[-1].size!=base[-1].size:raise ValueError('Dimensions originales et retouchées incohérentes.')
            member=archive.getinfo('source.png')
            if member.file_size>160_000_000:raise ValueError('Image source trop volumineuse.')
            source=_load_image(archive.read(member),40_000_000)
            options=dict(data['settings'])
            if 'background' in options:options['background']=tuple(options['background'])
            settings=Settings(**options)
            return frames,base,source,settings,data.get('class','Artwork')
    if path.name=='asset.json':
        data=json.loads(path.read_text(encoding='utf-8'));count=data['frames']
        if not isinstance(count,int) or not 1<=count<=256:raise ValueError('Nombre d’images invalide.')
        frames=[_load_image((path.parent/f'frame-{i:03d}.png').read_bytes()) for i in range(count)]
        if any(im.size!=frames[0].size for im in frames):raise ValueError('Les cellules doivent partager la même taille.')
        w,h=frames[0].size
        if count==1:source=frames[0].copy();settings=Settings(mode='Écran 512 × 256' if (w,h)==(512,256) else 'Sprite')
        else:
            columns=max(k for k in range(1,min(count,max(1,4096//w))+1) if count%k==0)
            rows=count//columns
            source=Image.new('RGBA',(columns*w,rows*h))
            for i,image in enumerate(frames):source.alpha_composite(image,((i%columns)*w,(i//columns)*h))
            settings=Settings(mode='Planche de sprites',cell_width=w,cell_height=h)
        return frames,[im.copy() for im in frames],source,settings,data.get('class','Artwork')
    raise ValueError('Ouvrez un projet .nandart ou le fichier asset.json d’un export.')
