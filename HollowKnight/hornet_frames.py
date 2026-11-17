"""Import native sprite-sheet cells and emit a cached, bounded Jack sprite blitter."""
from pathlib import Path
from functools import lru_cache
from PIL import Image, ImageDraw, ImageOps

HERE = Path(__file__).resolve().parent
BACKGROUND = {(121, 156, 155), (95, 124, 130)}
# idle x2, walk x4, rising/falling, windup/strike/recovery/end.
CELLS = [(9,3,41,35), (12,101,44,131),
         (10,52,42,83), (46,52,78,83), (80,52,112,83), (115,52,147,83),
         (13,146,36,179), (69,146,101,179),
         (9,240,41,275), (46,240,78,275), (82,240,114,275), (119,240,151,275)]


@lru_cache(maxsize=1)
def frames():
    atlas = Image.open(HERE / 'assets/hornet-sheet.png').convert('RGB')
    result = []
    for index, box in enumerate(CELLS):
        cell = atlas.crop(box)
        cut = Image.new('RGBA', cell.size)
        head = []
        for y in range(cell.height):
            for x in range(cell.width):
                rgb = cell.getpixel((x, y))
                if rgb in BACKGROUND:
                    continue
                # White mask stays white. Cloak, outlines and needle become black.
                white = min(rgb) > 200
                cut.putpixel((x,y), (255,255,255,255) if white else (0,0,0,255))
                if white and y < cell.height // 2:
                    head.append(x)
        # All cells use the same scale and feet baseline; align by the head, not needle.
        size = (round(cut.width * 1.33), round(cut.height * 1.33))
        cut = cut.resize(size, Image.Resampling.NEAREST)
        center = round(sum(head) / len(head) * 1.33)
        canvas = Image.new('RGBA', (80,48))
        canvas.paste(cut, (40-center, 48-cut.height))
        if index in (9,10):
            # A clear forward thrust, with a light edge against dark cave scenery.
            d = ImageDraw.Draw(canvas)
            tip = 2 if index == 9 else 8
            d.line([(tip,31),(37,31)], fill='white', width=3)
            d.line([(tip,31),(37,31)], fill='black', width=1)
            d.line([(tip,31),(tip+5,29)], fill='black', width=1)
        result.append(canvas)
    return result


def sprite(frame):
    return frames()[frame].copy()


def generate():
    originals = frames()
    images = [ImageOps.mirror(im) for im in originals] + list(originals)
    count = 80 // 8 * 48
    lines = ['// Generated from assets/hornet-sheet.png by hornet_frames.py.',
             'class Sprite {', '    static Array ink, mask;',
             '    static int loaded;', '    function void init() {',
             '        if (~(ink = 0)) { return; }',
             f'        let ink = Array.new({count});', f'        let mask = Array.new({count});',
             '        let loaded = -1;', '        return;', '    }',
             '    function void load(int frame, int facing) {',
             '        var int id, i;', '        let id = frame + (facing * 12);',
             '        if (id = loaded) { return; }', '        let i = 0;',
             f'        while (i < {count}) {{', '            let ink[i] = 0;',
             '            let mask[i] = 0;', '            let i = i + 1;', '        }']
    for n in range(len(images)):
        lines.append(f'        if (id = {n}) {{ do Sprite.pose{n}(); }}')
    lines += ['        let loaded = id;', '        return;', '    }']
    for n, im in enumerate(images):
        lines.append(f'    function void pose{n}() {{')
        for y in range(48):
            for x in range(0,80,8):
                mask = ink = 0
                for bit in range(8):
                    r,g,b,a = im.getpixel((x+bit,y))
                    if a:
                        mask |= 1 << bit
                        if r < 128: ink |= 1 << bit
                i = y*10+x//8
                if mask: lines.append(f'        let mask[{i}] = {mask};')
                if ink: lines.append(f'        let ink[{i}] = {ink};')
        lines += ['        return;', '    }']
    lines += ['''    function void draw(int x, int y, int facing, int frame) {
        var Array screen;
        var int row, col, source, pixel, address, m, v;
        do Sprite.load(frame, facing);
        let screen = 16384;
        let x = x - 24;
        let source = 0;
        let row = 0;
        while (row < 48) {
            let col = 0;
            while (col < 10) {
                let pixel = x + (col * 8);
                let m = mask[source];
                if ((~(m = 0)) & (pixel > -1) & (pixel < 512)) {
                    let v = ink[source];
                    let address = ((y + row) * 32) + (pixel / 16);
                    if ((pixel & 8) = 8) {
                        let m = m * 256;
                        let v = v * 256;
                    }
                    let screen[address] = (screen[address] & (~m)) | v;
                }
                let source = source + 1;
                let col = col + 1;
            }
            let row = row + 1;
        }
        return;
    }
}''']
    (HERE / 'Sprite.jack').write_text('\n'.join(lines)+'\n')
    # Readable animation reference of the exact imported monochrome game poses.
    previews = []
    for im in [images[i] for i in (0,1,0,1,2,3,4,5,6,7,8,9,10,11,0)]:
        bg = Image.new('RGBA', im.size, 'white')
        bg.alpha_composite(im)
        previews.append(bg.convert('RGB').resize((320,192),Image.Resampling.NEAREST))
    target = HERE / 'previews'
    target.mkdir(exist_ok=True)
    previews[0].save(target / 'hornet-animations.gif',save_all=True,
                     append_images=previews[1:],duration=120,loop=0)
    return originals
