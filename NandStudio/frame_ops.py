"""Frame imports and exact, gap-free source sheets for editable sequences."""
from dataclasses import replace
from pathlib import Path
from PIL import Image,ImageOps
from core import convert


IMAGE_TYPES=[('Images','*.png *.jpg *.jpeg *.bmp *.webp *.gif *.tif *.tiff'),('Tous','*.*')]


def read_frames(paths,size,settings,limit,opaque=False):
    if len(paths)>limit:raise ValueError(f'Import limité à {limit} image(s) supplémentaires.')
    raw=[];binary=[]
    options=replace(settings,mode='Sprite',scale=1)
    for path in paths:
        with Image.open(path) as source:
            image=ImageOps.exif_transpose(source).convert('RGBA')
        image=ImageOps.contain(image,size,Image.Resampling.NEAREST)
        canvas=Image.new('RGBA',size,'white' if opaque else (0,0,0,0))
        canvas.alpha_composite(image,((size[0]-image.width)//2,(size[1]-image.height)//2))
        raw.append(canvas);binary.append(convert(canvas,options)[0])
    return raw,binary


def source_sheet(originals,settings):
    if not 1<=len(originals)<=256:raise ValueError('Une séquence doit contenir de 1 à 256 frames.')
    w,h=originals[0].size;count=len(originals)
    if any(image.size!=(w,h) for image in originals):raise ValueError('Dimensions de frames incohérentes.')
    columns=max(k for k in range(1,min(count,max(1,4096//w))+1) if count%k==0)
    sheet=Image.new('RGBA',(columns*w,(count//columns)*h))
    for i,image in enumerate(originals):sheet.paste(image,((i%columns)*w,(i//columns)*h))
    return sheet,replace(settings,mode='Planche de sprites',cell_width=w,cell_height=h,scale=1)
