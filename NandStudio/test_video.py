"""Real FFmpeg integration tests using synthetic local footage only."""
from pathlib import Path
import json
import subprocess
import tempfile
import unittest
import zipfile
from PIL import Image
from video import (VideoSettings,VideoClip,VideoEngine,Cancelled,find_ffmpeg,
                   probe_video,save_clip,load_clip,WINDOWS_FLAGS)


class VideoFormatTests(unittest.TestCase):
    def test_packed_roundtrip_and_memory(self):
        frames=(bytes([0])*1024,bytes([255])*1024)
        clip=VideoClip(128,64,8.0,frames,'test.mp4')
        self.assertEqual(clip.memory_bytes,2048)
        self.assertEqual(clip.image(0).getpixel((0,0)),0)
        self.assertEqual(clip.image(1).getpixel((0,0)),255)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'movie.nandvideo';save_clip(path,clip)
            loaded=load_clip(path)
            self.assertEqual(loaded.frames,frames);self.assertEqual(loaded.fps,8)
            self.assertEqual(loaded.duration,.25)

    def test_limits_and_corrupt_container(self):
        for settings in (VideoSettings(duration=121),VideoSettings(fps=31),VideoSettings(start=-1),VideoSettings(width=192),VideoSettings(duration=float('inf'))):
            with self.assertRaises(ValueError):settings.validate()
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'bad.nandvideo'
            with zipfile.ZipFile(path,'w') as archive:
                archive.writestr('video.json',json.dumps({'format':'nandvideo','version':1,'width':512,'height':256,'fps':8,'frames':2}))
                archive.writestr('frames.bin',b'bad')
            with self.assertRaises(ValueError):load_clip(path)


@unittest.skipUnless(find_ffmpeg(),'FFmpeg non installé : tests natifs ignorés')
class FFmpegTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.root=Path(cls.temp.name);cls.path=cls.root/'fixture.mp4'
        command=[find_ffmpeg(),'-y','-hide_banner','-loglevel','error','-f','lavfi',
                 '-i','testsrc2=size=640x360:rate=24','-t','2','-c:v','mpeg4','-q:v','3',str(cls.path)]
        result=subprocess.run(command,capture_output=True,timeout=20,**WINDOWS_FLAGS)
        if result.returncode:raise RuntimeError(result.stderr.decode(errors='replace'))

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def test_real_decode_seek_binary_inversion_and_probe(self):
        info=probe_video(self.path);self.assertEqual((info['width'],info['height']),(640,360))
        progress=[]
        normal=VideoEngine().decode(self.path,VideoSettings(start=.5,duration=.5,fps=8,width=256),lambda a,b:progress.append((a,b)))
        inverse=VideoEngine().decode(self.path,VideoSettings(start=.5,duration=.5,fps=8,width=256,invert=True))
        self.assertEqual(len(normal.frames),4);self.assertEqual(normal.memory_bytes,4*4096)
        self.assertTrue(progress)
        for a,b in zip(normal.frames,inverse.frames):self.assertEqual(bytes(v^255 for v in a),b)
        self.assertEqual(normal.image(0).getpixel((0,0)),255)

    def test_bayer_and_full_resolution(self):
        clip=VideoEngine().decode(self.path,VideoSettings(duration=.5,fps=4,width=512,dither='Bayer 4 × 4',fit='Remplir'))
        self.assertEqual(len(clip.frames),2);self.assertEqual(len(clip.frames[0]),16384)
        self.assertEqual(clip.image(0).size,(512,256))

    def test_cancellation_stops_native_process(self):
        engine=VideoEngine()
        with self.assertRaises(Cancelled):
            engine.decode(self.path,VideoSettings(duration=2,fps=24,width=512),lambda a,b:engine.cancel())
        self.assertIsNone(engine.process)
        with self.assertRaises(Cancelled):engine.decode(self.path,VideoSettings())

    def test_real_mp4_and_gif_exports(self):
        clip=VideoEngine().decode(self.path,VideoSettings(duration=.5,fps=8,width=128))
        for suffix in ('.mp4','.gif'):
            target=self.root/('export'+suffix);VideoEngine().export_movie(clip,target)
            info=probe_video(target);self.assertEqual((info['width'],info['height']),(128,64))
            self.assertTrue(target.stat().st_size>0)
