"""Correctness checks for accelerated paths and coalesced background work."""
from pathlib import Path
import random
import tempfile
import threading
import time
import unittest
from PIL import Image, ImageEnhance
from core import Settings,convert,words,pixels
from machines import HackCPU,VM,assemble,framebuffer
from jobs import LatestWorker


class OptimizedTests(unittest.TestCase):
    def test_bayer_matches_scalar_reference_at_threshold_extremes(self):
        rng=random.Random(20);im=Image.frombytes('L',(23,19),bytes(rng.randrange(256) for _ in range(23*19)))
        matrix=((0,8,2,10),(12,4,14,6),(3,11,1,9),(15,7,13,5))
        for threshold in (0,1,90,128,165,254,255):
            out=convert(im,Settings(mode='Sprite',dither='Bayer 4 × 4',threshold=threshold))[0]
            expected=bytes(255 if im.getpixel((x,y))>=threshold+(matrix[y%4][x%4]-7.5)*12 else 0
                           for y in range(im.height) for x in range(im.width))
            self.assertEqual(out.getchannel('R').tobytes(),expected)

    def test_color_mask_matches_scalar_reference(self):
        rng=random.Random(80);im=Image.new('RGBA',(31,17))
        for y in range(im.height):
            for x in range(im.width):
                im.putpixel((x,y),tuple(rng.randrange(110,151) for _ in range(3))+(rng.randrange(256),))
        for tolerance in (0,8,16,255):
            bg=(120,130,140)
            out=convert(im,Settings(mode='Sprite',remove_background=True,background=bg,tolerance=tolerance))[0]
            expected=bytes(255 if a>=128 and max(abs(c-k) for c,k in zip((r,g,b),bg))>tolerance else 0
                           for r,g,b,a in pixels(im))
            self.assertEqual(out.getchannel('A').tobytes(),expected)

    def test_framebuffer_signed_words_and_packing(self):
        rng=random.Random(9);ram=[0]*32768
        ram[16384:24576]=[rng.randrange(-32768,32768) for _ in range(8192)]
        expected=bytes(0 if value&(1<<bit) else 255 for value in ram[16384:24576] for bit in range(16))
        image=framebuffer(ram)
        self.assertEqual(image.tobytes(),expected)
        self.assertEqual(words(image),[w&65535 for w in ram[16384:24576]])

    def test_batch_cpu_matches_single_step_and_yields(self):
        rng=random.Random(8)
        from machines import COMP
        rom=[]
        for _ in range(500):
            rom.extend([rng.randrange(100,200),0xe000|(rng.choice(list(COMP.values()))<<6)|(rng.randrange(8)<<3)])
        rom+=assemble('@0\n0;JMP')
        slow=HackCPU(rom);fast=HackCPU(rom)
        for _ in range(5000):slow.step()
        fast.run(5000)
        self.assertEqual((slow.a,slow.d,slow.pc,slow.steps,slow.ram),(fast.a,fast.d,fast.pc,fast.steps,fast.ram))
        machine=HackCPU(assemble('@0\n0;JMP'))
        machine.run(10_000_000,max_seconds=.002)
        self.assertGreater(machine.steps,0);self.assertLess(machine.steps,10_000_000)

    def test_vm_batch_yields_without_ending_program(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'Main.vm';p.write_text('function Main.main 0\nlabel AGAIN\ngoto AGAIN\n')
            vm=VM([p]);vm.run(10_000_000,max_seconds=.002)
            self.assertGreater(vm.steps,0);self.assertLess(vm.steps,10_000_000);self.assertFalse(vm.halted)

    def test_worker_discards_old_result_and_skips_intermediate_jobs(self):
        worker=LatestWorker();gate=threading.Event();called=[]
        try:
            worker.submit(lambda:(gate.wait(2),'old')[1])
            worker.submit(lambda:called.append('intermediate'))
            version=worker.submit(lambda:'new')
            gate.set();result=None;deadline=time.monotonic()+3
            while result is None and time.monotonic()<deadline:
                result=worker.poll();time.sleep(.001)
            self.assertEqual(result,(version,'new',None));self.assertEqual(called,[])
            worker.submit(lambda:'stale');worker.invalidate();time.sleep(.01)
            self.assertIsNone(worker.poll())
        finally:gate.set();worker.close()
