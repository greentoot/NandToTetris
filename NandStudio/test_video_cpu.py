"""The CPU must perform every SCREEN write; the host only feeds ordinary RAM."""
import unittest
from PIL import Image,ImageDraw
from core import words
from machines import framebuffer
from video import VideoClip
from video_cpu import VideoCPU


class VideoCPUTests(unittest.TestCase):
    def clip(self):
        image=Image.new('1',(128,64),1)
        ImageDraw.Draw(image).rectangle((3,5,42,37),fill=0)
        other=Image.new('1',(128,64),0)
        return VideoClip(128,64,8,(image.tobytes(),other.tobytes()),'cpu-test')

    def test_host_feeds_ram_and_cpu_draws_exact_pixels(self):
        clip=self.clip();cpu=VideoCPU(clip)
        cpu.ram[24576]=128
        self.assertTrue(cpu.feed(0))
        self.assertEqual(cpu.ram[16384:24576],[0]*8192)
        self.assertEqual(cpu.steps,0)
        expected=clip.image(0).resize((512,256),Image.Resampling.NEAREST)
        self.assertEqual(cpu.ram[16:8208],words(expected))
        cpu.run(120000)
        self.assertEqual(cpu.ram[16384:24576],words(expected))
        self.assertEqual(framebuffer(cpu.ram).tobytes(),expected.convert('L').tobytes())
        self.assertEqual(cpu.ram[24576],128)
        self.assertEqual(cpu.completed,1)
        self.assertEqual(cpu.ram[0],0)
        self.assertGreater(cpu.steps,100000)

    def test_multiple_frames_loop_and_step_match_batch(self):
        clip=self.clip();batch=VideoCPU(clip,1);manual=VideoCPU(clip,1)
        batch.run(10000)
        for _ in range(batch.steps):manual.step()
        self.assertEqual(manual.ram,batch.ram)
        self.assertEqual((manual.pc,manual.a,manual.d),(batch.pc,batch.a,batch.d))
        batch.run(120000)
        self.assertEqual(batch.displayed_index,1)
        batch.next_due=0;batch.run(120000)
        self.assertEqual(batch.completed,2)
        self.assertEqual(batch.displayed_index,0)
        self.assertLess(len(batch.rom),50)

    def test_pacing_does_not_skip_or_busy_wait(self):
        cpu=VideoCPU(self.clip());cpu.run(120000)
        cpu.next_due=float('inf');steps=cpu.steps
        cpu.run(120000)
        self.assertEqual(cpu.steps,steps)
        self.assertEqual(cpu.completed,1)

    def test_full_resolution_and_invalid_clip(self):
        image=Image.new('1',(512,256),1);image.putpixel((511,255),0)
        cpu=VideoCPU(VideoClip(512,256,12,(image.tobytes(),)))
        cpu.run(120000)
        self.assertEqual(cpu.ram[24575],32768)
        self.assertEqual(cpu.ram[16384],0)
        with self.assertRaises(ValueError):VideoCPU(VideoClip(128,64,8,()))
