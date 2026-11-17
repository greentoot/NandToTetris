"""Pixel editing, history, portable documents and edited export integration."""
from pathlib import Path
import tempfile
import unittest
from PIL import Image
from artwork import EditDocument,PALETTE,pixel_overrides,apply_overrides,save_artwork,load_artwork
from core import Settings,export_project,convert,words
from machines import HackCPU,assemble


class ArtworkTests(unittest.TestCase):
    def test_strokes_undo_redo_and_new_branch(self):
        doc=EditDocument([Image.new('RGBA',(8,8),'white'),Image.new('RGBA',(8,8),'white')])
        doc.begin(0);doc.line(0,(0,0),(7,7),PALETTE['Noir']);doc.finish()
        self.assertEqual(doc.frames[0].getpixel((4,4)),PALETTE['Noir'])
        doc.begin(1);doc.fill(1,(2,2),PALETTE['Transparent']);doc.finish()
        self.assertEqual(doc.frames[1].getpixel((0,0))[3],0)
        self.assertEqual(doc.undo(),1);self.assertEqual(doc.frames[1].getpixel((0,0))[3],255)
        self.assertEqual(doc.undo(),0);self.assertEqual(doc.frames[0].getpixel((4,4)),PALETTE['Blanc'])
        self.assertEqual(doc.redo(),0);self.assertEqual(doc.frames[0].getpixel((4,4)),PALETTE['Noir'])
        doc.begin(0);doc.line(0,(0,7),(7,0),PALETTE['Noir']);doc.finish()
        self.assertIsNone(doc.redo())
        # Source assets remain independent from editor snapshots.
        doc.undo();self.assertEqual(doc.frames[0].getpixel((0,7)),PALETTE['Blanc'])

    def test_overrides_preserve_color_and_alpha_after_conversion(self):
        base=[Image.new('RGBA',(8,8),'white')];edited=[base[0].copy()]
        edited[0].putpixel((0,0),PALETTE['Noir']);edited[0].putpixel((1,1),PALETTE['Transparent'])
        patches=pixel_overrides(base,edited)
        self.assertEqual(len(patches[0][1]),2)
        new=apply_overrides([Image.new('RGBA',(8,8),'black')],patches)[0]
        self.assertEqual(new.getpixel((0,0)),PALETTE['Noir'])
        self.assertEqual(new.getpixel((1,1)),PALETTE['Transparent'])
        self.assertEqual(base[0].getpixel((0,0)),PALETTE['Blanc'])

    def test_nandart_roundtrip_contains_source_base_and_edits(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Image.new('RGBA',(16,8),'white');settings=Settings(mode='Planche de sprites',cell_width=8,cell_height=8)
            base=convert(source,settings);frames=[im.copy() for im in base]
            frames[1].putpixel((7,7),PALETTE['Noir'])
            path=Path(tmp)/'saved.nandart';save_artwork(path,frames,base,source,settings,'Artwork')
            actual,originals,raw,loaded,name=load_artwork(path)
            self.assertEqual(name,'Artwork');self.assertEqual(loaded,settings)
            self.assertEqual(raw.tobytes(),source.tobytes())
            self.assertEqual(actual[1].tobytes(),frames[1].tobytes())
            self.assertEqual(originals[1].tobytes(),base[1].tobytes())
            self.assertEqual(len(list(Path(tmp).iterdir())),1)

    def test_reopen_exported_assets_and_export_edited_pixels_to_cpu(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/'project';image=Image.new('RGBA',(512,256),'white')
            image.putpixel((30,20),PALETTE['Noir'])
            export_project(folder,'example.png',Settings(),[image],'Artwork')
            frames,base,source,settings,name=load_artwork(folder/'asset.json')
            doc=EditDocument(frames);doc.begin(0)
            doc.line(0,(30,20),(30,20),PALETTE['Blanc'])
            doc.line(0,(40,20),(40,20),PALETTE['Noir']);doc.finish()
            target=Path(tmp)/'edited';export_project(target,'saved',settings,doc.frames,name)
            cpu=HackCPU(assemble((target/'Artwork.asm').read_text()));cpu.run(150000)
            self.assertEqual(cpu.ram[16384:24576],words(doc.frames[0]))
            self.assertEqual(doc.frames[0].getpixel((30,20)),PALETTE['Blanc'])
