"""Small original, code-authored pixel graphics for the converter's examples."""
from pathlib import Path
import random
from PIL import Image, ImageDraw


def main():
    root=Path(__file__).parent/'examples';root.mkdir(exist_ok=True)
    im=Image.new('RGB',(512,256),'white');d=ImageDraw.Draw(im);rng=random.Random(12)
    d.ellipse((205,22,293,110),fill='black')
    d.ellipse((219,17,301,99),fill='white')
    for _ in range(54):
        x=rng.randrange(70,445);y=rng.randrange(8,145)
        d.rectangle((x,y,x+1,y+1),fill='black')
    d.polygon([(0,190),(67,139),(103,161),(157,115),(238,193),(312,131),(386,180),(461,127),(511,171),(511,256),(0,256)],fill='black')
    d.polygon([(51,220),(124,169),(166,198),(226,151),(308,213),(380,172),(469,225),(511,217),(511,256),(0,256),(0,237)],fill='white')
    d.polygon([(0,0),(44,0),(65,68),(40,115),(51,207),(91,256),(0,256)],fill='black')
    d.polygon([(511,0),(468,0),(450,55),(468,125),(449,207),(422,256),(511,256)],fill='black')
    for x in (0,22,482,500):d.line((x,0,x+9,236),fill='white',width=2)
    d.rectangle((0,234,512,256),fill='black')
    for x in range(8,510,17):d.rectangle((x,240,x+8,241),fill='white')
    for x,y,w in ((103,197,69),(238,172,64),(357,203,74)):
        d.rectangle((x,y,x+w,y+7),fill='black');d.line((x+3,y+3,x+w-3,y+3),fill='white')
    d.rounded_rectangle((193,214,223,234),radius=5,fill='black')
    d.rectangle((198,219,218,225),fill='white');d.rectangle((201,219,203,224),fill='black')
    d.rectangle((213,219,215,224),fill='black')
    im.save(root/'grotte.png')
    sheet=Image.new('RGBA',(128,96))
    for i in range(12):
        cell=Image.new('RGBA',(32,32));p=ImageDraw.Draw(cell);step=(i%4)-1
        p.rectangle((8,6,24,18),fill='black');p.rectangle((10,8,22,16),fill='white')
        p.rectangle((12,10,14,13),fill='black');p.rectangle((19,10,21,13),fill='black')
        p.line((16,2,16,5),fill='black',width=2);p.rectangle((15,1,17,2),fill='black')
        p.rectangle((11,19,21,25),fill='black');p.line((10,20,5,22+step),fill='black',width=2)
        p.line((23,20,27,19-step),fill='black',width=2)
        p.line((13,25,11+step,30),fill='black',width=2);p.line((19,25,21-step,30),fill='black',width=2)
        if i>=8:p.line((25,19,31,19),fill='black',width=2)
        sheet.alpha_composite(cell,((i%4)*32,(i//4)*32))
    sheet.save(root/'sprites.png')


if __name__=='__main__':main()
