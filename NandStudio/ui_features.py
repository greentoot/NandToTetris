"""Asynchronous workshop UI. All Tk objects stay on the main thread."""
import json
import tkinter as tk
from tkinter import filedialog
from pathlib import Path
from PIL import Image, ImageTk, ImageDraw, ImageOps
from core import Settings, convert, asm_screen, jack_screen, jack_asset
from artwork import apply_overrides

CYAN='#65e1ce';CARD='#222a3b';MUTED='#94a0b8'


class StudioFeatures:
    def schedule_convert(self):
        if self.convert_job:self.root.after_cancel(self.convert_job)
        self.convert_job=self.root.after(140,self.reconvert)

    def reconvert(self):
        if self.convert_job:self.root.after_cancel(self.convert_job);self.convert_job=None
        if self.source is None:return
        try:
            settings=self.current_settings();source=self.source
            self.converting=True;self.export_button.state(['disabled'])
            self.status.set('Conversion en cours.')
            self.progress.start(12)
            self.convert_worker.submit(lambda:(convert(source,settings),settings,source))
        except (ValueError,tk.TclError) as error:
            self.convert_worker.invalidate();self.code_worker.invalidate();self.converting=False
            self.frames=[];self.preview.itemconfigure(self.preview_item,image='')
            self.status.set(str(error))

    def poll_workers(self):
        if self.closed:return
        result=self.convert_worker.poll()
        if result:
            version,data,error=result;self.converting=False
            if error:
                self.frames=[];self.preview.itemconfigure(self.preview_item,image='')
                self.status.set(str(error));self.export_button.state(['disabled'])
            else:
                fresh,self.accepted_settings,self.accepted_source=data
                self.base_frames=list(fresh)
                self.frames=apply_overrides(fresh,self.edit_overrides);self.generation+=1
                self.index%=len(self.frames)
                self.preview_cache.clear();self.thumb_cache.clear();self.code_cache.clear()
                self.code_worker.invalidate()
                frame=self.frames[self.index]
                self.stats.set(f'{frame.width} × {frame.height} px, {len(self.frames)} image(s), 1 bit + transparence')
                self.export_button.state(['!disabled'])
                self.sync_asset_controls()
                self.draw_preview();self.draw_filmstrip();self.schedule_code()
                self.status.set('Conversion terminée.')
        code=self.code_worker.poll()
        if code:
            version,data,error=code
            if error:self.status.set(str(error))
            else:
                key,text=data;self.cache_put(self.code_cache,key,text,8);self.apply_code(text)
        if not self.converting and self.future is None:self.progress.stop()
        self.root.after(30,self.poll_workers)

    @staticmethod
    def cache_put(cache,key,value,limit=32):
        cache[key]=value;cache.move_to_end(key)
        while len(cache)>limit:cache.popitem(last=False)
        # Bound enlarged preview textures by pixel count as well as item count.
        if hasattr(value,'width'):
            while len(cache)>1 and sum(v.width()*v.height() for v in cache.values())>8_000_000:
                cache.popitem(last=False)
        return value

    def set_view(self,value):
        self.source_view.set(value)
        for name,button in self.view_buttons.items():
            button.configure(style='Accent.TButton' if name==value else 'TButton')
        self.draw_preview()
        if value=='Comparer':self.status.set('Original à gauche, résultat à droite.')

    def original_frame(self,index=None):
        index=self.index if index is None else index
        image=self.accepted_source;settings=self.accepted_settings
        if settings.mode=='Planche de sprites':
            columns=image.width//settings.cell_width
            x=(index%columns)*settings.cell_width;y=(index//columns)*settings.cell_height
            image=image.crop((x,y,x+settings.cell_width,y+settings.cell_height))
        size=self.frames[index].size
        if settings.mode!='Écran 512 × 256':return image.resize(size,Image.Resampling.NEAREST)
        if settings.fit=='Remplir':return ImageOps.fit(image,size,Image.Resampling.LANCZOS)
        if settings.fit=='Étirer':return image.resize(size,Image.Resampling.LANCZOS)
        fitted=ImageOps.contain(image,size,Image.Resampling.LANCZOS)
        bg=Image.new('RGBA',size,'white')
        bg.alpha_composite(fitted,((size[0]-fitted.width)//2,(size[1]-fitted.height)//2))
        return bg

    def draw_preview(self):
        if not self.frames:return
        frame=self.frames[self.index];view=self.source_view.get()
        width=frame.width*(2 if view=='Comparer' else 1);height=frame.height
        w=max(1,self.preview.winfo_width()-24);h=max(1,self.preview.winfo_height()-24)
        scale=min(w/width,h/height) if self.zoom.get()=='Ajuster' else int(self.zoom.get().split()[0])/100
        size=(max(1,int(width*scale)),max(1,int(height*scale)))
        key=(self.generation,self.index,view,size);photo=self.preview_cache.get(key)
        if photo is None:
            bg=Image.new('RGBA',(width,height),'#e5e9f1');d=ImageDraw.Draw(bg)
            for y in range(0,height,8):
                for x in range(0,width,8):
                    if (x//8+y//8)%2:d.rectangle((x,y,x+7,y+7),fill='#b9c1ce')
            if view=='Original':bg.alpha_composite(self.original_frame())
            elif view=='Comparer':
                bg.alpha_composite(self.original_frame());bg.alpha_composite(frame,(frame.width,0))
            else:bg.alpha_composite(frame)
            photo=self.cache_put(self.preview_cache,key,ImageTk.PhotoImage(bg.resize(size,Image.Resampling.NEAREST)))
        self.preview_photo=photo
        ww=max(self.preview.winfo_width(),size[0]+24);hh=max(self.preview.winfo_height(),size[1]+24)
        self.preview.itemconfigure(self.preview_item,image=photo)
        self.preview.coords(self.preview_item,(ww-size[0])/2,(hh-size[1])/2)
        self.preview.configure(scrollregion=(0,0,ww,hh))
        self.frame_label.set(f'Image {self.index+1} / {len(self.frames)}')

    def draw_filmstrip(self):
        self.filmstrip.delete('all')
        if not self.frames:return
        self.thumb_refs=[];available=max(72,self.filmstrip.winfo_width())
        count=min(12,max(1,available//64))
        self.thumb_page=(self.index//count)*count;self.thumb_count=count
        for i in range(self.thumb_page,min(len(self.frames),self.thumb_page+count)):
            key=(self.generation,i);photo=self.thumb_cache.get(key)
            if photo is None:
                im=self.frames[i].copy();im.thumbnail((46,42),Image.Resampling.NEAREST)
                bg=Image.new('RGBA',(48,44),'#bcc4d3');bg.alpha_composite(im,((48-im.width)//2,(44-im.height)//2))
                photo=self.cache_put(self.thumb_cache,key,ImageTk.PhotoImage(bg),48)
            self.thumb_refs.append(photo);x=(i-self.thumb_page)*64+8
            self.filmstrip.create_rectangle(x-2,3,x+50,49,outline=CYAN if i==self.index else CARD,width=2)
            self.filmstrip.create_image(x,5,image=photo,anchor='nw')
            self.filmstrip.create_text(x+24,57,text=str(i+1),fill=CYAN if i==self.index else MUTED,font=('Segoe UI',8))

    def select_thumbnail(self,event):
        index=getattr(self,'thumb_page',0)+event.x//64
        if self.frames and index<len(self.frames) and index<self.thumb_page+self.thumb_count:
            self.index=index;self.draw_preview();self.draw_filmstrip();self.schedule_code()

    def change_frame(self,delta):
        if self.frames:
            self.index=(self.index+delta)%len(self.frames)
            self.draw_preview();self.draw_filmstrip()
            if not self.playing:self.schedule_code()

    def toggle_animation(self):
        self.playing=not self.playing
        self.play_button.configure(text='Pause' if self.playing else 'Lire')
        if self.animation_job:self.root.after_cancel(self.animation_job);self.animation_job=None
        if self.playing:self.animate()
        else:self.schedule_code()

    def animate(self):
        self.animation_job=None
        if self.closed or not self.playing:return
        self.change_frame(1)
        try:fps=max(1,min(30,self.fps.get()))
        except tk.TclError:fps=8
        self.animation_job=self.root.after(round(1000/fps),self.animate)

    def schedule_code(self):
        if self.code_job:self.root.after_cancel(self.code_job)
        self.code_job=self.root.after(120,lambda:self.show_code(self.kind.get()))

    def show_code(self,kind):
        self.code_job=None;self.kind.set(kind)
        if not self.frames:return
        frame=self.frames[self.index];settings=self.accepted_settings;name=self.class_name.get()
        key=(self.generation,self.index,kind,name)
        if key in self.code_cache:
            self.code_worker.invalidate();self.apply_code(self.code_cache[key]);return
        count=len(self.frames)
        def generate():
            if kind=='JSON':text=json.dumps({'settings':settings.__dict__,'frames':count},ensure_ascii=False,indent=2)
            elif kind=='ASM':text=asm_screen(frame)
            else:text=jack_screen(frame,name) if settings.mode=='Écran 512 × 256' else jack_asset([frame],name,True)
            return key,text
        self.code_worker.submit(generate)

    def apply_code(self,text):
        self.current_code=text;visible=text[:16000]
        if len(text)>16000:visible+='\n// Aperçu limité. L’export contient le code complet.\n'
        self.code.configure(state='normal');self.code.delete('1.0','end');self.code.insert('1.0',visible);self.code.configure(state='disabled')

    def save_preset(self):
        try:settings=self.current_settings()
        except Exception as error:self.error(error);return
        path=filedialog.asksaveasfilename(defaultextension='.json',filetypes=[('Réglages Studio','*.json')])
        if path:Path(path).write_text(json.dumps(settings.__dict__,ensure_ascii=False,indent=2),encoding='utf-8')

    def load_preset(self):
        path=filedialog.askopenfilename(filetypes=[('Réglages Studio','*.json')])
        if not path:return
        try:
            settings=Settings(**json.loads(Path(path).read_text(encoding='utf-8')))
            self.background=tuple(settings.background)
            for key,var in self.vars.items():var.set(getattr(settings,key))
            self.reconvert()
        except Exception as error:self.error(error)
