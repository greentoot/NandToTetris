"""Withdrawn-window tests: no desktop capture, input injection or app control."""
import tkinter as tk
import time
import unittest
from pathlib import Path
import tempfile
from types import SimpleNamespace
from editor import ArtworkEditor
from video import VideoClip
from app import Studio
from machines import HackCPU,assemble
from artwork import save_artwork,load_artwork


class UITests(unittest.TestCase):
    def test_async_workshop_and_render_caches(self):
        try:root=tk.Tk()
        except tk.TclError as exc:self.skipTest(str(exc))
        root.withdraw();app=Studio(root);errors=[]
        root.report_callback_exception=lambda *args:errors.append(str(args[1]))
        def settle():
            deadline=time.monotonic()+5
            while time.monotonic()<deadline:
                root.update();time.sleep(.002)
                if app.convert_job is None and not app.converting:return
            self.fail('Async conversion timeout')
        try:
            settle();self.assertEqual(len(app.frames),1)
            app.sprite_example();settle();self.assertEqual(len(app.frames),12)
            for view in ('Original','Comparer','Résultat'):app.set_view(view)
            app.zoom.set('200 %');app.draw_preview()
            before=app.preview_photo;app.draw_preview();self.assertIs(before,app.preview_photo)
            app.change_frame(1);self.assertEqual(app.index,1)
            app.toggle_animation();self.assertIsNotNone(app.animation_job)
            app.toggle_animation();self.assertIsNone(app.animation_job)
            for threshold in (40,90,180):app.vars['threshold'].set(threshold);app.reconvert()
            settle();self.assertEqual(app.accepted_settings.threshold,180)
            app.machine=HackCPU(assemble('@0\n0;JMP'));app.draw_machine()
            photo=app.machine_photo;app.draw_machine();self.assertIs(photo,app.machine_photo)
            app.machine.ram[16384]=1;app.draw_machine();self.assertIsNot(photo,app.machine_photo)
            app.vars['cell_width'].set(512);app.reconvert();settle();self.assertEqual(app.frames,[])
            app.vars['cell_width'].set(32);app.reconvert();settle();self.assertEqual(len(app.frames),12)
            # Paned layouts expose real draggable sashes and remain resettable.
            for pane in (app.work_split,app.canvas_code_split,app.emu_split):
                self.assertEqual(len(pane.panes()),2)
            app.reset_layout()
            # Applying retouches updates the exported document and survives same-size conversion.
            edited=[im.copy() for im in app.frames];edited[0].putpixel((0,0),(0,0,0,255))
            version=app.generation;app.commit_edits(edited,version)
            self.assertEqual(app.frames[0].getpixel((0,0)),(0,0,0,255))
            with self.assertRaises(ValueError):app.commit_edits(edited,version)
            app.vars['threshold'].set(100);app.reconvert();settle()
            self.assertEqual(app.frames[0].getpixel((0,0)),(0,0,0,255))
            with tempfile.TemporaryDirectory() as tmp:
                path=Path(tmp)/'art.nandart'
                save_artwork(path,app.frames,app.base_frames,app.accepted_source,app.accepted_settings,'Artwork')
                app.accept_artwork(load_artwork(path),path)
                self.assertEqual(len(app.frames),12)
                self.assertEqual(app.frames[0].getpixel((0,0)),(0,0,0,255))
            # Exercise the editor's own widgets while its toplevel stays withdrawn.
            editor=ArtworkEditor(root,app.frames,0,app.generation,app.commit_edits)
            editor.window.withdraw()
            try:
                editor.zoom.set('400 %');editor.draw()
                event=SimpleNamespace(x=12+5*4+1,y=12+5*4+1)
                editor.color.set('Noir');editor.stroke_start(event);editor.stroke_end()
                self.assertEqual(editor.document.frames[0].getpixel((5,5)),(0,0,0,255))
                self.assertTrue(editor.apply())
                self.assertEqual(app.frames[0].getpixel((5,5)),(0,0,0,255))
            finally:editor.window.destroy()
            # Dedicated video playback and transfer work without a real desktop window.
            frames=(bytes([0])*1024,bytes([255])*1024)
            app.video.accept_clip(VideoClip(128,64,8.0,frames,'test'))
            app.video.set_index(1);self.assertEqual(app.video.index,1)
            app.video.toggle_play();self.assertTrue(app.video.playing)
            app.video.pause();self.assertFalse(app.video.playing)
            app.video.test_cpu();app.pause_machine()
            self.assertEqual(app.loaded_kind,'video')
            self.assertEqual(app.machine.start,1)
            app.machine.run(120000)
            self.assertEqual(app.machine.completed,1)
            app.reset_machine()
            self.assertEqual(app.machine.completed,0)
            self.assertEqual(app.machine.start,1)
            self.assertEqual(app.machine.steps,0)
            app.single_step();self.assertEqual(app.machine.steps,1)
            app.video.send_frame();self.assertEqual(app.frames[0].size,(128,64))
            self.assertEqual(app.frames[0].getpixel((0,0)),(255,255,255,255))
            # A video sequence transfers frames, and a longer clip is trimmed from the active frame.
            sequence=tuple(bytes([i % 256])*1024 for i in range(257))
            app.video.accept_clip(VideoClip(128,64,8.0,sequence,'sequence'))
            app.video.set_index(7);app.video.send_sequence()
            deadline=time.monotonic()+5
            while time.monotonic()<deadline and app.video.future is not None:
                root.update();time.sleep(.002)
            self.assertEqual(len(app.frames),256)
            self.assertEqual(app.frames[0].convert('1').tobytes()[0],7)
            self.assertIn('256 frames envoyées',app.status.get())
            self.assertEqual(errors,[])
        finally:app.close()
