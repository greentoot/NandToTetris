"""Sequence editing through real callbacks, with all test windows withdrawn."""
import tempfile
import time
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from app import Studio
from artwork import save_artwork,load_artwork
from core import Settings,convert
from frame_ops import read_frames,source_sheet
from video import save_clip,load_clip


class FrameImportTests(unittest.TestCase):
    def test_normalization_alpha_threshold_order_and_sheet_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths=[Path(tmp)/f'{i}.png' for i in range(2)]
            Image.new('RGBA',(4,8),(90,90,90,255)).save(paths[0])
            Image.new('RGBA',(8,8),'white').save(paths[1])
            settings=Settings(mode='Sprite',threshold=100)
            raw,frames=read_frames(paths,(8,8),settings,2)
            self.assertEqual(frames[0].getpixel((0,0))[3],0)
            self.assertEqual(frames[0].getpixel((2,0)),(0,0,0,255))
            self.assertEqual(frames[1].getpixel((0,0)),(255,255,255,255))
            source,options=source_sheet(raw,settings)
            result=convert(source,options)
            self.assertEqual([im.tobytes() for im in result],[im.tobytes() for im in frames])
            _,opaque=read_frames(paths[:1],(8,8),settings,2,opaque=True)
            self.assertEqual(opaque[0].getpixel((0,0)),(255,255,255,255))
            with self.assertRaises(ValueError):read_frames(paths,(8,8),settings,1)


class FrameActionUITests(unittest.TestCase):
    def test_add_delete_undo_reconvert_save_and_cpu_sequence(self):
        try:root=tk.Tk()
        except tk.TclError as exc:self.skipTest(str(exc))
        root.withdraw();app=Studio(root);errors=[]
        root.report_callback_exception=lambda *args:errors.append(str(args[1]))
        def settle():
            deadline=time.monotonic()+5
            while time.monotonic()<deadline:
                root.update();time.sleep(.002)
                if app.future is None and app.video.future is None and app.convert_job is None and not app.converting:return
            self.fail('Frame operation timeout')
        try:
            settle()
            with tempfile.TemporaryDirectory() as tmp:
                white=Image.new('RGBA',(8,8),'white');settings=Settings(mode='Sprite')
                app.accept_artwork(([white.copy()],[white.copy()],white.copy(),settings,'Frames'),Path(tmp)/'initial.png')
                edited=[white.copy()];edited[0].putpixel((0,0),(0,0,0,255))
                app.commit_edits(edited,app.generation)
                black=Path(tmp)/'black.png';Image.new('RGBA',(8,8),'black').save(black)
                with patch('artwork_ui.filedialog.askopenfilenames',return_value=(str(black),)):
                    app.add_frames();settle()
                self.assertEqual(len(app.frames),2);self.assertEqual(app.index,1)
                self.assertEqual(app.frames[0].getpixel((0,0)),(0,0,0,255))
                app.reconvert();settle();self.assertEqual(len(app.frames),2)
                app.index=0;app.delete_frame();self.assertEqual(len(app.frames),1)
                app.reconvert();settle();self.assertEqual(len(app.frames),1)
                self.assertEqual(app.frames[0].getpixel((0,0)),(0,0,0,255))
                app.undo_frames();self.assertEqual(len(app.frames),2)
                self.assertEqual(app.frames[0].getpixel((0,0)),(0,0,0,255))
                target=Path(tmp)/'edited.nandart'
                save_artwork(target,app.frames,app.base_frames,app.accepted_source,app.accepted_settings,'Frames')
                restored=load_artwork(target)
                self.assertEqual(len(restored[0]),2)
                self.assertEqual(len(convert(restored[2],restored[3])),2)
                app.index=1;app.delete_frame();app.delete_frame()
                self.assertEqual(len(app.frames),1)
                app.undo_frames();self.assertEqual(len(app.frames),2)
                # Video sequences can also be created from still images, without FFmpeg.
                with patch('video_ui.filedialog.askopenfilenames',return_value=(str(black),str(black))):
                    app.video.add_frames();settle()
                self.assertEqual(len(app.video.clip.frames),2)
                app.video.set_index(1);app.video.delete_frame()
                self.assertEqual(len(app.video.clip.frames),1)
                app.video.delete_frame();self.assertEqual(len(app.video.clip.frames),1)
                app.video.undo_frames();self.assertEqual(len(app.video.clip.frames),2)
                app.video.test_cpu();app.pause_machine()
                app.video.delete_frame()
                app.video.test_cpu();app.pause_machine()
                self.assertEqual(len(app.machine.clip.frames),1)
                packed=Path(tmp)/'edited.nandvideo';save_clip(packed,app.video.clip)
                self.assertEqual(len(load_clip(packed).frames),1)
                self.assertEqual(float(app.video.timeline['to']),0)
            self.assertEqual(errors,[])
        finally:app.close()
