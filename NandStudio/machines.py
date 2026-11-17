"""Small Hack CPU and cooperative VM interpreters, independent of the GUI."""
from pathlib import Path
import math
import time
from PIL import Image, ImageDraw, ImageFont
from array import array
import sys
from core import BIT_TRANSLATION

COMP={'0':0b0101010,'1':0b0111111,'-1':0b0111010,'D':0b0001100,
      'A':0b0110000,'M':0b1110000,'!D':0b0001101,'!A':0b0110001,'!M':0b1110001,
      '-D':0b0001111,'-A':0b0110011,'-M':0b1110011,'D+1':0b0011111,
      'A+1':0b0110111,'M+1':0b1110111,'D-1':0b0001110,'A-1':0b0110010,
      'M-1':0b1110010,'D+A':0b0000010,'D+M':0b1000010,'D-A':0b0010011,
      'D-M':0b1010011,'A-D':0b0000111,'M-D':0b1000111,'D&A':0b0000000,
      'D&M':0b1000000,'D|A':0b0010101,'D|M':0b1010101}
JUMP={'':0,'JGT':1,'JEQ':2,'JGE':3,'JLT':4,'JNE':5,'JLE':6,'JMP':7}


def signed(value): return ((int(value)+32768)&65535)-32768


def assemble(source):
    lines=[line.split('//')[0].strip() for line in source.splitlines()]
    lines=[line for line in lines if line]
    symbols={'SP':0,'LCL':1,'ARG':2,'THIS':3,'THAT':4,'SCREEN':16384,'KBD':24576}
    symbols.update({f'R{i}':i for i in range(16)})
    pc=0
    for line in lines:
        if line.startswith('(') and not line.endswith(')'):
            raise ValueError('Déclaration de label ASM invalide : '+line)
        if line.startswith('(') and line.endswith(')'):
            name=line[1:-1]
            if not name or name in symbols or not (name[0].isalpha() or name[0] in '_.$:') or not all(c.isalnum() or c in '_.$:' for c in name):
                raise ValueError('Label invalide ou dupliqué : '+name)
            symbols[name]=pc
        else: pc+=1
    if pc>32768: raise ValueError(f'ROM : {pc:,} instructions, limite CPU Hack 32 768. Utilisez la version VM ou simplifiez l’image.')
    output=[];variable=16
    for line in lines:
        if line.startswith('('): continue
        if line.startswith('@'):
            name=line[1:]
            if name.isdecimal(): value=int(name)
            else:
                if not name or not (name[0].isalpha() or name[0] in '_.$:') or not all(c.isalnum() or c in '_.$:' for c in name):
                    raise ValueError('Symbole invalide : '+name)
                if name not in symbols:
                    if variable>=16384: raise ValueError('Trop de variables ASM.')
                    symbols[name]=variable;variable+=1
                value=symbols[name]
            if not 0<=value<32768: raise ValueError('Adresse hors plage : '+line)
            output.append(value)
        else:
            dest='';jump='';comp=line.replace(' ','')
            if '=' in comp: dest,comp=comp.split('=',1)
            if ';' in comp: comp,jump=comp.split(';',1)
            if comp not in COMP or jump not in JUMP or any(c not in 'ADM' for c in dest) or len(set(dest))!=len(dest):
                raise ValueError('Instruction ASM invalide : '+line)
            d=(4 if 'A'in dest else 0)|(2 if 'D'in dest else 0)|(1 if 'M'in dest else 0)
            output.append(0xe000|(COMP[comp]<<6)|(d<<3)|JUMP[jump])
    return output


def framebuffer(ram):
    data=array('H',(word&65535 for word in ram[16384:24576]))
    if sys.byteorder != 'little': data.byteswap()
    return Image.frombytes('1',(512,256),data.tobytes().translate(BIT_TRANSLATION)).convert('L')


class HackCPU:
    def __init__(self,rom):
        if len(rom)>32768: raise ValueError('La ROM dépasse 32 768 instructions.')
        self.rom=list(rom);self.ram=[0]*32768
        self.a=self.d=self.pc=self.steps=0
        self.halted=False;self.location='CPU Hack';self.wait_until=0

    def step(self):
        if not 0<=self.pc<len(self.rom): self.halted=True;return
        instruction=self.rom[self.pc];old_a=self.a
        self.pc=(self.pc+1)&32767;self.steps+=1
        if not instruction&0x8000: self.a=instruction;return
        if instruction&0xe000 != 0xe000: raise ValueError('Instruction CPU réservée.')
        c=(instruction>>6)&127
        x=self.d;y=self.ram[old_a&32767] if c&64 else old_a
        # The six ALU control bits are zx,nx,zy,ny,f,no.
        if c&32: x=0
        if c&16: x=(~x)&65535
        if c&8: y=0
        if c&4: y=(~y)&65535
        value=(x+y if c&2 else x&y)&65535
        if c&1: value=(~value)&65535
        dest=(instruction>>3)&7
        if dest&1 and (old_a&32767)!=24576: self.ram[old_a&32767]=value
        if dest&2: self.d=value
        if dest&4: self.a=value
        jump=instruction&7;v=signed(value)
        if (False,v>0,v==0,v>=0,v<0,v!=0,v<=0,True)[jump]: self.pc=old_a&32767

    def run(self,budget,max_seconds=None):
        # Registers stay local through the batch; step() remains the reference/debug path.
        rom=self.rom;ram=self.ram;a=self.a;d=self.d;pc=self.pc
        deadline=time.perf_counter()+max_seconds if max_seconds is not None else None
        executed=0
        for i in range(budget):
            if self.halted:break
            if deadline is not None and i%256==0 and time.perf_counter()>=deadline:break
            if not 0<=pc<len(rom):self.halted=True;break
            instruction=rom[pc];old_a=a;pc=(pc+1)&32767;executed+=1
            if not instruction&0x8000:a=instruction;continue
            if instruction&0xe000 != 0xe000:raise ValueError('Instruction CPU réservée.')
            c=(instruction>>6)&127;x=d;y=ram[old_a&32767] if c&64 else old_a
            if c&32:x=0
            if c&16:x=(~x)&65535
            if c&8:y=0
            if c&4:y=(~y)&65535
            value=(x+y if c&2 else x&y)&65535
            if c&1:value=(~value)&65535
            dest=(instruction>>3)&7
            if dest&1 and (old_a&32767)!=24576:ram[old_a&32767]=value
            if dest&2:d=value
            if dest&4:a=value
            jump=instruction&7;v=signed(value)
            if (False,v>0,v==0,v>=0,v<0,v!=0,v<=0,True)[jump]:pc=old_a&32767
        self.a=a;self.d=d;self.pc=pc;self.steps+=executed


class VM:
    """Cooperative VM with native educational OS adapters (not the official emulator)."""
    def __init__(self,paths,entry=None):
        self.ram=[0]*32768;self.functions={};self.statics={};self.frames=[];self.stack=[]
        self.free=[(2048,14336)];self.allocations={};self.steps=0
        self.halted=False;self.wait_until=0;self.location='VM';self.output=''
        self.color=True;self.cursor=(0,0)
        for path in sorted(map(Path,paths)):
            if path.name=='final.vm': continue
            current=None
            for lineno,raw in enumerate(path.read_text(encoding='utf-8-sig').splitlines(),1):
                cmd=raw.split('//')[0].split()
                if not cmd: continue
                if cmd[0]=='function':
                    if len(cmd)!=3 or int(cmd[2])<0: raise ValueError(f'{path.name}:{lineno} : fonction invalide')
                    current=cmd[1]
                    if current in self.functions: raise ValueError('Fonction dupliquée : '+current)
                    self.functions[current]={'count':int(cmd[2]),'body':[],'labels':{},'owner':path.stem}
                elif current:
                    fun=self.functions[current]
                    if cmd[0]=='label': fun['labels'][cmd[1]]=len(fun['body'])
                    fun['body'].append(cmd)
                else: raise ValueError(f'{path.name}:{lineno} : instruction hors fonction')
        entry=entry or ('Sys.init' if 'Sys.init'in self.functions else 'Main.main')
        self.push_frame(entry,[])

    def push_frame(self,name,args):
        if name not in self.functions: raise ValueError('Fonction VM introuvable : '+name)
        f=self.functions[name];parent=self.frames[-1] if self.frames else None
        self.frames.append({'name':name,'pc':0,'local':[0]*f['count'],'args':list(args),
                            'this':parent['this'] if parent else 0,'that':parent['that'] if parent else 0,
                            'base':len(self.stack)})
        if len(self.frames)>2000: raise ValueError('Profondeur d’appels VM excessive.')

    def alloc(self,size):
        if size<1: raise ValueError('Allocation de taille nulle ou négative.')
        for i,(start,length) in enumerate(self.free):
            if length>=size:
                self.free.pop(i)
                if length>size: self.free.insert(i,(start+size,length-size))
                self.allocations[start]=size;self.ram[start:start+size]=[0]*size
                return start
        raise ValueError('Mémoire dynamique épuisée.')

    def dealloc(self,start):
        if start not in self.allocations: raise ValueError('Libération d’une allocation inconnue.')
        self.free.append((start,self.allocations.pop(start)));self.free.sort();merged=[]
        for a,n in self.free:
            if merged and sum(merged[-1])==a:
                p,q=merged.pop();merged.append((p,q+n))
            else: merged.append((a,n))
        self.free=merged
        return 0

    def pixel(self,x,y):
        if not 0<=x<512 or not 0<=y<256: return
        addr=16384+y*32+x//16;mask=1<<(x%16)
        self.ram[addr]=signed(self.ram[addr]|mask if self.color else self.ram[addr]&~mask)

    def line(self,x,y,xx,yy):
        if any(abs(v)>2048 for v in (x,y,xx,yy)): raise ValueError('Coordonnées de dessin hors plage.')
        dx=abs(xx-x);dy=-abs(yy-y);sx=1 if x<xx else -1;sy=1 if y<yy else -1;err=dx+dy
        while True:
            self.pixel(x,y)
            if (x,y)==(xx,yy): break
            e=2*err
            if e>=dy: err+=dy;x+=sx
            if e<=dx: err+=dx;y+=sy

    def print_char(self,code):
        if code==128: self.cursor=(self.cursor[0]+1,0);return 0
        if code==129: self.cursor=(self.cursor[0],max(0,self.cursor[1]-1));return 0
        self.output+=chr(code&255)
        row,col=self.cursor
        glyph=Image.new('1',(8,11),0);ImageDraw.Draw(glyph).text((0,-1),chr(code&255),fill=1,font=ImageFont.load_default())
        for y in range(11):
            for x in range(8):
                self.color=bool(glyph.getpixel((x,y)));self.pixel(col*8+x,(row%23)*11+y)
        self.color=True;self.cursor=(row+(col>=63),0 if col>=63 else col+1)
        return 0

    def native(self,name,args):
        if name in ('Memory.init','Math.init','Screen.init','Output.init','Keyboard.init'): return 0
        if name in ('Array.new','Memory.alloc'): return self.alloc(args[0])
        if name in ('Array.dispose','Memory.deAlloc'): return self.dealloc(args[0])
        if name=='Memory.peek': return self.ram[self.address(args[0])]
        if name=='Memory.poke': self.ram[self.address(args[0])]=signed(args[1]);return 0
        if name=='Keyboard.keyPressed': return self.ram[24576]
        if name=='Math.multiply': return signed(args[0]*args[1])
        if name=='Math.divide': return signed(int(args[0]/args[1]))
        if name=='Math.sqrt': return math.isqrt(max(0,args[0]))
        if name=='Math.abs': return signed(abs(args[0]))
        if name=='Math.min': return min(args)
        if name=='Math.max': return max(args)
        if name=='Sys.wait': self.wait_until=time.monotonic()+max(0,args[0])/1000;return 0
        if name=='Sys.halt': self.halted=True;return 0
        if name=='Sys.error': raise ValueError('Sys.error : '+str(args[0]))
        if name=='Screen.clearScreen': self.ram[16384:24576]=[0]*8192;return 0
        if name=='Screen.setColor': self.color=bool(args[0]);return 0
        if name=='Screen.drawPixel': self.pixel(*args);return 0
        if name=='Screen.drawLine': self.line(*args);return 0
        if name=='Screen.drawRectangle':
            x,y,xx,yy=args
            for row in range(max(0,y),min(255,yy)+1): self.line(x,row,xx,row)
            return 0
        if name=='Screen.drawCircle':
            x,y,r=args
            if r<0 or r>512: raise ValueError('Rayon de cercle hors plage.')
            for dy in range(-r,r+1):
                dx=math.isqrt(r*r-dy*dy);self.line(x-dx,y+dy,x+dx,y+dy)
            return 0
        if name=='Output.moveCursor': self.cursor=tuple(args);return 0
        if name=='Output.printChar': return self.print_char(args[0])
        if name=='Output.println': return self.print_char(128)
        if name=='Output.backSpace': return self.print_char(129)
        if name=='Output.printInt':
            for c in str(args[0]): self.print_char(ord(c))
            return 0
        return NotImplemented

    @staticmethod
    def address(value):
        if not 0<=value<32768: raise ValueError('Adresse RAM VM hors plage : '+str(value))
        return value

    def step(self):
        if not self.frames: self.halted=True;return
        f=self.frames[-1];fun=self.functions[f['name']];body=fun['body'];pc=f['pc']
        if not 0<=pc<len(body): raise ValueError('Fonction sans return : '+f['name'])
        c=body[pc];f['pc']+=1;self.steps+=1;op=c[0];self.location=f"{f['name']}:{pc}"
        if op in ('push','pop'):
            seg=c[1];i=int(c[2])
            if i<0: raise ValueError('Index VM négatif.')
            if seg=='constant':
                if op!='push' or i>32767: raise ValueError('Constante VM invalide.')
                self.stack.append(i);return
            if seg=='local': target,offset=f['local'],0
            elif seg=='argument': target,offset=f['args'],0
            elif seg=='static': target,offset=self.statics.setdefault(fun['owner'],[0]*256),0
            elif seg=='temp':
                if i>7: raise ValueError('Index temp hors plage.')
                target,offset=self.ram,5
            elif seg in ('this','that'): target,offset=self.ram,f[seg]
            elif seg=='pointer':
                if i>1: raise ValueError('Index pointer hors plage.')
                field='this' if i==0 else 'that'
                if op=='push': self.stack.append(f[field])
                else: f[field]=self.stack.pop()
                return
            else: raise ValueError('Segment VM inconnu : '+seg)
            index=offset+i
            if not 0<=index<len(target): raise ValueError('Accès au segment VM hors plage.')
            if op=='push': self.stack.append(signed(target[index]))
            else: target[index]=signed(self.stack.pop())
        elif op=='call':
            n=int(c[2])
            if n<0 or n>len(self.stack): raise ValueError('Arguments VM manquants.')
            args=self.stack[-n:] if n else []
            if n: del self.stack[-n:]
            result=self.native(c[1],args)
            if result is NotImplemented: self.push_frame(c[1],args)
            else: self.stack.append(signed(result))
        elif op=='return':
            result=self.stack.pop();self.stack[f['base']:]=[];self.frames.pop()
            if self.frames: self.stack.append(result)
            else: self.halted=True
        elif op in ('label','goto','if-goto'):
            if op=='goto' or (op=='if-goto' and self.stack.pop()): f['pc']=fun['labels'][c[1]]
        elif op in ('neg','not'):
            a=self.stack.pop();self.stack.append(signed(-a if op=='neg' else ~a))
        else:
            b=self.stack.pop();a=self.stack.pop()
            if op=='add': v=a+b
            elif op=='sub': v=a-b
            elif op=='and': v=a&b
            elif op=='or': v=a|b
            elif op=='eq': v=-int(a==b)
            elif op=='lt': v=-int(a<b)
            elif op=='gt': v=-int(a>b)
            else: raise ValueError('Instruction VM inconnue : '+op)
            self.stack.append(signed(v))

    def run(self,budget,max_seconds=None):
        deadline=time.perf_counter()+max_seconds if max_seconds is not None else None
        for i in range(budget):
            if self.halted:break
            if self.wait_until:
                if time.monotonic()<self.wait_until:break
                self.wait_until=0
            if deadline is not None and i%256==0 and time.perf_counter()>=deadline:break
            self.step()
