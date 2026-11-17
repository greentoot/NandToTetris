"""Deterministic image-to-Hack assets. No network service or AI is required."""
from dataclasses import dataclass, asdict
from pathlib import Path
import json
import keyword
import re
import zipfile
from collections import Counter
from functools import lru_cache
from array import array
import sys
from PIL import Image, ImageOps, ImageEnhance, ImageChops

# Hack low bit is the leftmost black pixel; Pillow stores high bits first, white=1.
BIT_TRANSLATION = bytes(255-int(f'{i:08b}'[::-1],2) for i in range(256))


@lru_cache(maxsize=16)
def bayer_maps(size, threshold):
    matrix=((0,8,2,10),(12,4,14,6),(3,11,1,9),(15,7,13,5))
    width,height=size
    rows=[];valid=[]
    for row in matrix:
        values=[threshold+(v*12)-90 for v in row]
        rows.append((bytes(max(0,min(255,v)) for v in values)*((width+3)//4))[:width])
        valid.append((bytes(255 if v<=255 else 0 for v in values)*((width+3)//4))[:width])
    return (Image.frombytes('L',size,b''.join(rows[y%4] for y in range(height))),
            Image.frombytes('L',size,b''.join(valid[y%4] for y in range(height))))


def pixels(image):
    # Pillow 12+ renamed getdata; keep compatibility with Pillow 10/11.
    return image.get_flattened_data() if hasattr(image,'get_flattened_data') else image.getdata()


@dataclass
class Settings:
    mode: str = 'Écran 512 × 256'
    threshold: int = 128
    contrast: float = 1.0
    invert: bool = False
    dither: str = 'Seuil'
    fit: str = 'Contenir'
    cell_width: int = 32
    cell_height: int = 32
    scale: int = 1
    remove_background: bool = False
    remove_checker: bool = False
    tolerance: int = 16
    background: tuple = (255, 255, 255)


def convert(source, settings):
    """Return RGBA frames with exact binary colors and optional transparency."""
    image = ImageOps.exif_transpose(source).convert('RGBA')
    if settings.remove_background or settings.remove_checker:
        colors=[tuple(settings.background)]
        if settings.remove_checker:
            sample=image.copy();sample.thumbnail((256,256),Image.Resampling.NEAREST)
            colors=[rgb[:3] for rgb,_ in Counter(pixels(sample)).most_common(2)]
        r,g,b,alpha=image.split()
        keep=Image.new('L',image.size,255)
        for color in colors:
            match=Image.new('L',image.size,255)
            for channel,key in zip((r,g,b),color):
                lut=[255 if abs(value-key)<=settings.tolerance else 0 for value in range(256)]
                match=ImageChops.darker(match,channel.point(lut))
            keep=ImageChops.darker(keep,ImageOps.invert(match))
        image.putalpha(ImageChops.multiply(alpha,keep))
    frames = []
    if settings.mode == 'Planche de sprites':
        w,h = settings.cell_width, settings.cell_height
        if not 1 <= w <= 512 or not 1 <= h <= 256:
            raise ValueError('Les cellules doivent mesurer entre 1 × 1 et 512 × 256.')
        if image.width < w or image.height < h:
            raise ValueError('La cellule dépasse la taille de l’image.')
        count = (image.width // w) * (image.height // h)
        if count > 256:
            raise ValueError('Plus de 256 cellules : augmentez la taille des cellules.')
        for y in range(0, image.height-h+1, h):
            for x in range(0, image.width-w+1, w):
                frames.append(image.crop((x,y,x+w,y+h)))
    else:
        frames = [image]
    output = []
    for frame in frames:
        if settings.mode == 'Écran 512 × 256':
            white = Image.new('RGBA', frame.size, 'white')
            white.alpha_composite(frame)
            if settings.fit == 'Remplir':
                frame = ImageOps.fit(white, (512,256), Image.Resampling.LANCZOS)
            elif settings.fit == 'Étirer':
                frame = white.resize((512,256), Image.Resampling.LANCZOS)
            else:
                white.thumbnail((512,256), Image.Resampling.LANCZOS)
                frame = Image.new('RGBA', (512,256), 'white')
                frame.alpha_composite(white, ((512-white.width)//2,(256-white.height)//2))
        else:
            if not 1 <= settings.scale <= 8:
                raise ValueError('Échelle attendue : 1 à 8.')
            size = (frame.width*settings.scale, frame.height*settings.scale)
            if size[0] > 512 or size[1] > 256:
                raise ValueError('Le sprite agrandi dépasse 512 × 256.')
            frame = frame.resize(size, Image.Resampling.NEAREST)
        alpha = frame.getchannel('A')
        gray = ImageEnhance.Contrast(frame.convert('L')).enhance(settings.contrast)
        if settings.invert: gray = ImageOps.invert(gray)
        if settings.dither == 'Floyd–Steinberg':
            gray = gray.point(lambda v: max(0,min(255,v+128-settings.threshold)))
            mono = gray.convert('1', dither=Image.Dither.FLOYDSTEINBERG).convert('L')
        elif settings.dither == 'Bayer 4 × 4':
            thresholds,valid=bayer_maps(gray.size,settings.threshold)
            diff=ImageChops.subtract(gray,thresholds,offset=1)
            mono=ImageChops.multiply(diff.point([0]+[255]*255),valid)
        else:
            mono = gray.point(lambda v: 255 if v >= settings.threshold else 0)
        result = Image.merge('RGBA',(mono,mono,mono,alpha.point(lambda v: 255 if v >=128 else 0)))
        output.append(result)
    return output


def screen_image(frame):
    bg = Image.new('RGBA',(512,256),'white')
    bg.alpha_composite(frame, ((512-frame.width)//2,(256-frame.height)//2))
    return bg.convert('1')


def words(image):
    image = screen_image(image) if image.size != (512,256) or image.mode == 'RGBA' else image
    if image.mode != '1': image=image.convert('1')
    data=array('H');data.frombytes(image.tobytes().translate(BIT_TRANSLATION))
    if sys.byteorder != 'little': data.byteswap()
    return data.tolist()


def valid_name(name):
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*',name) or name in {
        'Main','Sys','Screen','Math','Memory','Array','String','Keyboard','Output',
        'class','function','method','constructor','static','field','var','int','char',
        'boolean','void','true','false','null','this','let','do','if','else','while','return'}:
        raise ValueError('Nom de classe : lettre initiale puis lettres/chiffres/_, hors mots réservés et classes système.')
    return name


def literal(value):
    return str(value) if value < 32768 else '~'+str(65535-value)


def jack_asset(frames, name='Artwork', transparent=False):
    """Unrolled byte blits: no heap, any x coordinate, clipping on all screen edges."""
    valid_name(name)
    lines = ['// Generated by Nand Asset Studio. 1 bit = black; low bit is left.',
             f'class {name} {{',
             '    function void draw(int x, int y, int frame) {']
    for index in range(len(frames)):
        lines.append(f'        if (frame = {index}) {{ do {name}.frame{index}(x, y); }}')
    lines += ['        return;', '    }']
    for index,im in enumerate(frames):
        lines.append(f'    function void frame{index}(int x, int y) {{')
        parts = []
        for part,y0 in enumerate(range(0,im.height,16)):
            parts.append((part,y0))
            lines.append(f'        do {name}.f{index}p{part}(x, y);')
        lines += ['        return;', '    }']
        for part,y0 in parts:
            lines.append(f'    function void f{index}p{part}(int x, int y) {{')
            for y in range(y0,min(y0+16,im.height)):
                x=0
                while x < im.width:
                    r,g,b,a = im.getpixel((x,y))
                    if a == 0 and transparent:
                        x+=1
                        continue
                    black = a > 0 and r < 128
                    end=x+1
                    while end < im.width:
                        rr,gg,bb,aa = im.getpixel((end,y))
                        if aa == 0 and transparent: break
                        if (aa>0 and rr<128) != black: break
                        end+=1
                    lines.append(f'        do {name}.span(x + {x}, y + {y}, {end-x}, {str(black).lower()});')
                    x=end
            lines += ['        return;', '    }']
    lines += ['''    function void span(int x, int y, int length, boolean black) {
        var Array screen;
        var int address, bit, mask;
        if ((y < 0) | (y > 255)) { return; }
        let screen = 16384;
        while (length > 0) {
            if ((x > -1) & (x < 512)) {
                let address = (y * 32) + (x / 16);
                let bit = x & 15;
                let mask = 1;
                while (bit > 0) {
                    let mask = mask + mask;
                    let bit = bit - 1;
                }
                if (black) { let screen[address] = screen[address] | mask; }
                else { let screen[address] = screen[address] & (~mask); }
            }
            let x = x + 1;
            let length = length - 1;
        }
        return;
    }
}''']
    return '\n'.join(lines)+'\n'


def jack_screen(frame,name='Artwork'):
    """Fast full-screen renderer with direct video-memory word writes."""
    valid_name(name)
    data=words(frame)
    lines=[f'class {name} {{','    function void draw() {','        var Array screen;',
           '        var int i;','        let screen = 16384;','        let i = 0;',
           '        while (i < 8192) { let screen[i] = 0; let i = i + 1; }']
    for n in range(16): lines.append(f'        do {name}.part{n}(screen);')
    lines+=['        return;','    }']
    for n in range(16):
        lines.append(f'    function void part{n}(Array screen) {{')
        lines += [f'        let screen[{i}] = {literal(data[i])};'
                  for i in range(n*512,(n+1)*512) if data[i]]
        lines+=['        return;','    }']
    return '\n'.join(lines+['}'])+'\n'


def asm_screen(frame):
    # Clear first, even when loaded into an already-used machine.
    out=['// Generated by Nand Asset Studio', '@16384','D=A','@R13','M=D',
         '(CLEAR)','@R13','A=M','M=0','@R13','M=M+1','D=M','@24576','D=D-A','@CLEAR','D;JLT']
    last=None
    for i,value in enumerate(words(frame)):
        if not value: continue
        if value != last:
            out += ['@'+str(value if value<32768 else 65535-value),
                    'D=A' if value<32768 else 'D=!A']
            last=value
        out += ['@'+str(16384+i),'M=D']
    out+=['(END)','@END','0;JMP']
    return '\n'.join(out)+'\n'


def export_project(folder, source, settings, frames, name='Artwork'):
    """Create a complete, portable generated project. Compilation uses bundled tools."""
    from compiler import compile_jack
    from machines import assemble
    valid_name(name)
    folder=Path(folder)
    folder.mkdir(parents=True,exist_ok=True)
    if any(folder.iterdir()):
        raise ValueError('Choisissez un dossier vide pour éviter de remplacer un projet existant.')
    screen=settings.mode == 'Écran 512 × 256'
    code=jack_screen(frames[0],name) if screen else jack_asset(frames,name,True)
    (folder/(name+'.jack')).write_text(code,encoding='utf-8')
    args='' if screen else f'{(512-frames[0].width)//2}, {(256-frames[0].height)//2}, 0'
    main=f'class Main {{ function void main() {{ do {name}.draw({args}); while (true) {{ do Sys.wait(50); }} return; }} }}\n'
    (folder/'Main.jack').write_text(main)
    for path in folder.glob('*.jack'):
        compile_jack(path, folder/(path.stem+'.vm'))
    os_root=Path(__file__).parent/'vendor'/'os'
    for path in os_root.glob('*.vm'):
        (folder/path.name).write_bytes(path.read_bytes())
    for i,frame in enumerate(frames): frame.save(folder/f'frame-{i:03d}.png')
    asm=asm_screen(frames[0])
    (folder/'Artwork.asm').write_text(asm)
    warning=''
    try:
        rom=assemble(asm)
        (folder/'Artwork.hack').write_text('\n'.join(f'{v:016b}' for v in rom)+'\n')
    except ValueError as error:
        warning=str(error)
    if len(frames)>1:
        previews=[]
        for frame in frames:
            bg=Image.new('RGBA',frame.size,'white');bg.alpha_composite(frame)
            previews.append(bg.convert('RGB'))
        previews[0].save(folder/'animation.gif',save_all=True,append_images=previews[1:],duration=120,loop=0)
    screen_image(frames[0]).save(folder/'preview.png')
    (folder/'asset.json').write_text(json.dumps({'source':Path(source).name,'settings':asdict(settings),
        'frames':len(frames),'class':name,'width':frames[0].width,'height':frames[0].height,
        'cpu_warning':warning},indent=2,ensure_ascii=False),encoding='utf-8')
    (folder/'README.md').write_text(f'''# {name}

Généré avec Nand Asset Studio. Charger ce dossier dans le VM Emulator officiel,
Run et capture clavier. Le Main de démonstration affiche la première image.
Pour un sprite : `do {name}.draw(x, y, frame);` (frame commence à zéro).
Pour un écran : `do {name}.draw();`. Le sprite conserve les pixels transparents ;
le moteur du jeu doit restaurer le décor avant de le déplacer.

Artwork.asm / Artwork.hack dessinent la première image centrée sur un CPU Hack.
Ces fichiers sont des programmes d'image fixe, pas une traduction du Main Jack.
Les PNG, asset.json et animation.gif conservent les images et réglages exportés.
Le fond coloré peut être retiré par couleur ; un damier peint doit être retiré
couleur par couleur avant import si ses deux couleurs diffèrent.

{warning}
''',encoding='utf-8')
    return folder,warning


def zip_project(folder, destination):
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as output:
        for path in sorted(Path(folder).rglob('*')):
            if path.is_file(): output.write(path,Path(folder).name+'/'+path.relative_to(folder).as_posix())
