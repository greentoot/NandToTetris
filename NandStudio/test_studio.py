"""Run with: python -m unittest discover -s NandStudio -v"""
from pathlib import Path
import random
import tempfile
import unittest
from PIL import Image
from core import Settings, convert, words, asm_screen, jack_asset, export_project, zip_project, pixels
from compiler import compile_jack
from machines import HackCPU, VM, assemble, COMP, signed, framebuffer


def execute(machine,limit=2_000_000):
    for _ in range(limit//10000):
        machine.wait_until=0;machine.run(10000)
        if machine.halted:return
    raise AssertionError('Program did not return within its instruction budget')


class StudioTests(unittest.TestCase):
    def test_cpu_alu_destinations_and_jumps(self):
        rng=random.Random(19)
        for comp,bits in COMP.items():
            for _ in range(8):
                a=rng.randrange(200,500);d=rng.randrange(65536);memory=rng.randrange(65536)
                env={'D':d,'A':a,'M':memory}
                # Independent expression calculation for every documented ALU expression.
                if comp in ('0','1','-1'):expected=int(comp)&65535
                elif comp[0]=='!':expected=(~env[comp[1]])&65535
                elif comp[0]=='-':expected=(-env[comp[1]])&65535
                elif len(comp)==1:expected=env[comp]
                else:
                    left=env[comp[0]];right=1 if comp[2]=='1' else env[comp[2]]
                    expected={'+':lambda:left+right,'-':lambda:left-right,
                              '&':lambda:left&right,'|':lambda:left|right}[comp[1]]()&65535
                for dest in (0,1,2,4,7):
                    for jump in range(8):
                        m=HackCPU([0xe000|(bits<<6)|(dest<<3)|jump]);m.a=a;m.d=d;m.ram[a]=memory
                        m.step()
                        v=signed(expected);taken=(False,v>0,v==0,v>=0,v<0,v!=0,v<=0,True)[jump]
                        self.assertEqual(m.a,expected if dest&4 else a)
                        self.assertEqual(m.d,expected if dest&2 else d)
                        self.assertEqual(m.ram[a],expected if dest&1 else memory)
                        self.assertEqual(m.pc,a if taken else 1)

    def test_video_word_order_and_cpu_program(self):
        im=Image.new('RGBA',(512,256),'white')
        for point in [(0,0),(15,0),(16,0),(511,255)]:im.putpixel(point,(0,0,0,255))
        data=words(im);self.assertEqual(data[0],32769);self.assertEqual(data[1],1)
        rom=assemble(asm_screen(im));m=HackCPU(rom);m.ram[16384:24576]=[65535]*8192
        m.run(150000)
        self.assertEqual(m.ram[16384:24576],data)
        self.assertEqual(framebuffer(m.ram).getpixel((15,0)),0)
        self.assertEqual(framebuffer(m.ram).getpixel((14,0)),255)

    def test_threshold_alpha_grid_and_checker(self):
        im=Image.new('RGBA',(16,8),(0,0,0,0));im.putpixel((0,0),(150,150,150,255))
        frames=convert(im,Settings(mode='Planche de sprites',cell_width=8,cell_height=8))
        self.assertEqual(len(frames),2);self.assertEqual(frames[0].getpixel((0,0)),(255,255,255,255))
        self.assertEqual(frames[0].getpixel((1,0))[3],0)
        for dither in ('Seuil','Floyd–Steinberg','Bayer 4 × 4'):
            converted=convert(im,Settings(mode='Sprite',dither=dither))[0]
            self.assertTrue(set(pixels(converted.getchannel('R')))<={0,255})
        check=Image.new('RGBA',(16,16),(121,156,155,255))
        for y in range(8):
            for x in range(16):check.putpixel((x,y),(95,124,130,255))
        check.putpixel((4,4),(0,0,0,255))
        out=convert(check,Settings(mode='Sprite',remove_checker=True,tolerance=0))[0]
        self.assertEqual(sum(p[3]>0 for p in pixels(out)),1)

    def test_vm_frames_static_native_io_and_wait(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'Main.vm';p.write_text('''function Main.main 0
push constant 24576
call Memory.peek 1
push constant 5
call Main.double 1
add
pop static 0
push static 0
push constant 16384
pop pointer 1
pop that 0
push constant 50
call Sys.wait 1
pop temp 0
push constant 0
return
function Main.double 0
push argument 0
push argument 0
add
return
''')
            vm=VM([p]);vm.ram[24576]=128
            vm.run(1000);self.assertGreater(vm.wait_until,0);self.assertFalse(vm.halted)
            execute(vm);self.assertEqual(vm.ram[16384],138)
            self.assertEqual(vm.statics['Main'][0],138)

    def test_sprite_compilation_mask_arbitrary_position_and_clipping(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp);im=Image.new('RGBA',(8,5),(0,0,0,0))
            im.putpixel((0,0),(0,0,0,255));im.putpixel((1,0),(255,255,255,255));im.putpixel((7,4),(0,0,0,255))
            path=tmp/'Demo.jack';path.write_text(jack_asset([im],'Demo',True))
            compile_jack(path,tmp/'Demo.vm')
            for x,y in [(5,7),(-3,-2),(509,254)]:
                (tmp/'Main.vm').write_text(f'function Main.main 0\npush constant {abs(x)}\n'+('neg\n'if x<0 else '')+f'push constant {abs(y)}\n'+('neg\n'if y<0 else '')+'push constant 0\ncall Demo.draw 3\npop temp 0\npush constant 0\nreturn\n')
                vm=VM(tmp.glob('*.vm'));vm.ram[16384:24576]=[21845]*8192
                expected=list(vm.ram[16384:24576])
                for yy in range(5):
                    for xx in range(8):
                        r,g,b,a=im.getpixel((xx,yy));px=x+xx;py=y+yy
                        if a and 0<=px<512 and 0<=py<256:
                            at=py*32+px//16;mask=1<<(px%16)
                            expected[at]=((expected[at]|mask)if r<128 else(expected[at]&~mask))&65535
                execute(vm)
                self.assertEqual([v&65535 for v in vm.ram[16384:24576]],expected)

    def test_portable_export_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/'demo';im=Image.new('RGBA',(512,256),'white');im.putpixel((16,14),(0,0,0,255))
            export_project(folder,'example',Settings(),[im],'Sample')
            self.assertEqual(len(list(folder.glob('*.vm'))),10)
            cpu=HackCPU(assemble((folder/'Artwork.asm').read_text()));cpu.run(150000)
            self.assertEqual(cpu.ram[16384:24576],words(im))
            vm=VM(folder.glob('*.vm'),entry='Sample.draw');execute(vm)
            self.assertEqual([v&65535 for v in vm.ram[16384:24576]],words(im))
            zip_project(folder,Path(tmp)/'demo.zip');self.assertTrue((Path(tmp)/'demo.zip').exists())
            with self.assertRaises(ValueError):export_project(folder,'example',Settings(),[im],'Sample')

    def test_bad_inputs(self):
        for source in ('@32768\nD=A','D=banana','(X)\n(X)\n@X','(Unclosed'):
            with self.assertRaises(ValueError):assemble(source)
        with self.assertRaises(ValueError):assemble('@0\n'*32769)
        with self.assertRaises(ValueError):convert(Image.new('RGB',(2,2)),Settings(mode='Planche de sprites',cell_width=4))

    def test_compiler_error_preserves_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp);source=tmp/'Broken.jack';source.write_text('class Broken {')
            original=source.read_bytes()
            with self.assertRaises(ValueError):compile_jack(source,tmp/'Broken.vm')
            self.assertEqual(source.read_bytes(),original)
            self.assertFalse((tmp/'Broken.vm').exists())


if __name__=='__main__':unittest.main()
