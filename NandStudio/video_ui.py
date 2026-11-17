"""Dedicated asynchronous video workshop, independent from the image worker."""
from pathlib import Path
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
from collections import OrderedDict
from queue import Queue,Empty
import math
import time
import tkinter as tk
from tkinter import ttk,filedialog
from PIL import Image,ImageTk
from core import Settings
from video import VideoSettings,VideoClip,VideoEngine,Cancelled,MAX_FRAMES,find_ffmpeg,probe_video,save_clip,load_clip
from video_cpu import VideoCPU
from frame_ops import IMAGE_TYPES,read_frames,source_sheet

BG='#10131e';PANEL='#191e2c';CARD='#222a3b';TEXT='#eef2ff';MUTED='#94a0b8';CYAN='#65e1ce'


class VideoTab:
    def __init__(self,app,parent):
        self.app=app;self.root=app.root;self.parent=parent
        self.path=None;self.clip=None;self.index=0;self.playing=False;self.play_job=None
        self.future=None;self.pool=ThreadPoolExecutor(max_workers=1);self.events=Queue()
        self.engine=None;self.ffmpeg=find_ffmpeg();self.closed=False;self.photos=OrderedDict();self.scrubbing=False
        self.cancel_requested=False
        self.settings={}
        for key,value in VideoSettings().__dict__.items():
            cls=tk.BooleanVar if isinstance(value,bool) else tk.IntVar if isinstance(value,int) else tk.DoubleVar if isinstance(value,float) else tk.StringVar
            self.settings[key]=cls(value=value)
        self.status=tk.StringVar(value='Importer une vidéo locale, choisir un extrait, puis traiter.')
        self.info=tk.StringVar(value='Aucune vidéo importée')
        self.position=tk.StringVar(value='00:00.000 / 00:00.000')
        self.estimate=tk.StringVar();self.seek=tk.DoubleVar(value=0)
        self.build()
        for var in self.settings.values():var.trace_add('write',lambda *_:self.update_estimate())
        self.update_estimate();self.root.after(40,self.poll)

    def label(self,parent,text,color=TEXT,size=10):
        label=tk.Label(parent,text=text,bg=PANEL,fg=color,anchor='w',font=('Segoe UI',size))
        label.pack(fill='x',pady=(8,4));return label

    def build(self):
        self.split=tk.PanedWindow(self.parent,orient='horizontal',bg=CARD,sashwidth=9,showhandle=True,bd=0)
        self.split.pack(fill='both',expand=True,padx=12,pady=12)
        sidebar=tk.Frame(self.split,bg=PANEL,padx=8,pady=8);self.split.add(sidebar,minsize=280,width=320,stretch='never')
        actions=tk.Frame(sidebar,bg=PANEL);actions.pack(side='bottom',fill='x',pady=(9,0))
        scroll=tk.Canvas(sidebar,bg=PANEL,width=285,highlightthickness=0)
        scrollbar=ttk.Scrollbar(sidebar,orient='vertical',command=scroll.yview)
        scrollbar.pack(side='right',fill='y');scroll.pack(side='left',fill='both',expand=True)
        left=tk.Frame(scroll,bg=PANEL);item=scroll.create_window((0,0),window=left,anchor='nw',width=285)
        scroll.configure(yscrollcommand=scrollbar.set)
        left.bind('<Configure>',lambda e:scroll.configure(scrollregion=scroll.bbox('all')))
        scroll.bind('<Configure>',lambda e:scroll.itemconfigure(item,width=e.width))
        def wheel(event):
            widget=event.widget
            while widget is not None:
                if widget==left:scroll.yview_scroll(-1 if event.delta>0 else 1,'units');return 'break'
                widget=getattr(widget,'master',None)
        self.root.bind('<MouseWheel>',wheel,add='+')
        ttk.Button(left,text='Importer une vidéo',command=self.open_video,style='Accent.TButton').pack(fill='x')
        tk.Label(left,textvariable=self.info,bg=PANEL,fg=MUTED,wraplength=270,justify='left',anchor='w').pack(fill='x',pady=(9,5))
        self.label(left,'EXTRAIT (SECONDES)',CYAN)
        row=tk.Frame(left,bg=PANEL);row.pack(fill='x')
        for key,label in (('start','Début'),('duration','Durée')):
            cell=tk.Frame(row,bg=PANEL);cell.pack(side='left',fill='x',expand=True,padx=3)
            self.label(cell,label,MUTED,9)
            ttk.Spinbox(cell,from_=0 if key=='start' else .1,to=86400 if key=='start' else 120,
                        increment=.5,textvariable=self.settings[key],width=10).pack(fill='x')
        self.label(left,'VITESSE & RÉSOLUTION',CYAN)
        presets=tk.Frame(left,bg=PANEL);presets.pack(fill='x')
        ttk.Button(presets,text='Rapide',command=lambda:self.preset(256,8)).pack(side='left',fill='x',expand=True,padx=(0,4))
        ttk.Button(presets,text='Nand complet',command=lambda:self.preset(512,12)).pack(side='left',fill='x',expand=True)
        row=tk.Frame(left,bg=PANEL);row.pack(fill='x',pady=6)
        ttk.Combobox(row,textvariable=self.settings['width'],values=[128,256,512],state='readonly',width=8).pack(side='left')
        self.label(row,'pixels de large',MUTED,9).pack(side='left',padx=8)
        row=tk.Frame(left,bg=PANEL);row.pack(fill='x')
        ttk.Spinbox(row,from_=1,to=30,textvariable=self.settings['fps'],width=8).pack(side='left')
        self.label(row,'images / seconde',MUTED,9).pack(side='left',padx=8)
        self.label(left,'RENDU NOIR & BLANC',CYAN)
        for key,values in (('fit',['Contenir','Remplir','Étirer']),('dither',['Seuil rapide','Bayer 4 × 4'])):
            ttk.Combobox(left,textvariable=self.settings[key],values=values,state='readonly').pack(fill='x',pady=3)
        row=tk.Frame(left,bg=PANEL);row.pack(fill='x',pady=5)
        for key,label,lo,hi,step in (('threshold','Seuil',0,255,1),('contrast','Contraste',.2,3,.1)):
            cell=tk.Frame(row,bg=PANEL);cell.pack(side='left',fill='x',expand=True,padx=3)
            self.label(cell,label,MUTED,9)
            ttk.Spinbox(cell,from_=lo,to=hi,increment=step,textvariable=self.settings[key],width=9).pack(fill='x')
        ttk.Checkbutton(left,text='Inverser noir / blanc',variable=self.settings['invert']).pack(anchor='w',pady=5)
        tk.Label(left,textvariable=self.estimate,bg=CARD,fg=CYAN,justify='left',wraplength=270,padx=8,pady=9).pack(fill='x',pady=7)
        self.convert_button=ttk.Button(actions,text='Traiter l’extrait',command=self.process_video,style='Accent.TButton')
        self.convert_button.pack(fill='x',pady=4)
        ttk.Button(actions,text='Annuler le traitement',command=self.cancel).pack(fill='x',pady=3)
        ttk.Button(actions,text='Choisir FFmpeg',command=self.choose_ffmpeg).pack(fill='x',pady=(5,0))
        self.engine_label=self.label(actions,'FFmpeg prêt' if self.ffmpeg else 'FFmpeg manquant : choisir un exécutable',MUTED,9)
        right=tk.Frame(self.split,bg=PANEL,padx=12,pady=8);self.split.add(right,minsize=450,stretch='always')
        title=tk.Frame(right,bg=PANEL);title.pack(fill='x')
        self.label(title,'LECTEUR 1 BIT',CYAN).pack(side='left')
        ttk.Button(title,text='Envoyer l’image à l’atelier',command=self.send_frame).pack(side='right')
        ttk.Button(title,text='Envoyer les frames à l’atelier',command=self.send_sequence).pack(side='right',padx=5)
        self.canvas=tk.Canvas(right,bg='#080b12',highlightthickness=1,highlightbackground=CARD,height=330)
        self.canvas.pack(fill='both',expand=True,pady=10)
        self.item=self.canvas.create_image(0,0);self.canvas.bind('<Configure>',lambda e:self.draw())
        controls=tk.Frame(right,bg=PANEL);controls.pack(fill='x')
        ttk.Button(controls,text='Précédente',command=lambda:self.set_index(self.index-1)).pack(side='left')
        self.play_button=ttk.Button(controls,text='Lire',command=self.toggle_play);self.play_button.pack(side='left',padx=4)
        ttk.Button(controls,text='Suivante',command=lambda:self.set_index(self.index+1)).pack(side='left')
        tk.Label(controls,textvariable=self.position,bg=PANEL,fg=CYAN,font=('Consolas',10)).pack(side='right')
        frame_actions=tk.Frame(right,bg=PANEL);frame_actions.pack(fill='x',pady=(7,0))
        for text,command in [('Ajouter des frames',self.add_frames),('Supprimer la frame',self.delete_frame),('Annuler les frames',self.undo_frames)]:
            ttk.Button(frame_actions,text=text,command=command).pack(side='left',padx=(0,5))
        self.timeline=ttk.Scale(right,from_=0,to=1,variable=self.seek,command=self.scrub)
        self.timeline.pack(fill='x',pady=9)
        self.progress=ttk.Progressbar(right,mode='determinate',maximum=100);self.progress.pack(fill='x',pady=4)
        tk.Label(right,textvariable=self.status,bg=PANEL,fg=MUTED,justify='left',wraplength=650,anchor='w').pack(fill='x',pady=7)
        exports=tk.Frame(right,bg=PANEL);exports.pack(fill='x',pady=7)
        for text,command in [('Exporter .nandvideo',self.export_packed),('MP4',lambda:self.export_movie('.mp4')),
                             ('GIF',lambda:self.export_movie('.gif')),('Tester sur CPU Hack',self.test_cpu)]:
            ttk.Button(exports,text=text,command=command).pack(side='left',padx=(0,6))
        note=self.label(right,'Le test CPU copie les images depuis la RAM vers l’écran Hack. Sans audio.',MUTED,9)
        note.configure(wraplength=620,justify='left')

    def current_settings(self):return VideoSettings(**{key:var.get() for key,var in self.settings.items()})

    def preset(self,width,fps):self.settings['width'].set(width);self.settings['fps'].set(fps)

    def update_estimate(self):
        try:
            s=self.current_settings();s.validate();count=math.ceil(s.duration*s.fps);memory=count*s.width*(s.width//2)//8
            self.estimate.set(f'{s.width} × {s.width//2}, {count} images\nEnviron {memory/1048576:.1f} Mo en mémoire (1 bit)')
        except (ValueError,tk.TclError) as error:self.estimate.set(str(error))

    def choose_ffmpeg(self):
        path=filedialog.askopenfilename(title='Choisir l’exécutable FFmpeg',filetypes=[('FFmpeg','ffmpeg.exe ffmpeg'),('Tous','*.*')])
        if path:self.ffmpeg=path;self.engine_label.configure(text='FFmpeg sélectionné')

    def open_video(self):
        if self.future is not None:self.status.set('Annulez ou terminez le traitement en cours avant un nouvel import.');return
        path=filedialog.askopenfilename(title='Importer une vidéo locale',filetypes=[('Vidéos','*.mp4 *.mkv *.mov *.webm *.avi *.gif *.m4v *.nandvideo'),('Tous','*.*')])
        if not path:return
        self.pause()
        if Path(path).suffix.lower()=='.nandvideo':
            self.path=None;self.info.set(Path(path).name)
            self.start_job(lambda:load_clip(path),self.accept_clip);return
        self.path=Path(path);self.info.set(self.path.name)
        self.start_job(lambda:probe_video(path,self.ffmpeg),self.accept_info)

    def accept_info(self,info):
        duration=f'{info["duration"]:.1f} s' if info['duration'] else 'durée inconnue'
        dimensions=f'{info["width"]} × {info["height"]}' if info['width'] else ''
        self.info.set(f'{info["name"]}\n{dimensions}, {duration}')
        self.status.set('Source prête. Traiter l’extrait remplacera l’aperçu précédent.')

    def start_job(self,work,done,engine=None):
        if self.future is not None:self.status.set('Une tâche vidéo est déjà en cours.');return
        self.engine=engine;self.convert_button.state(['disabled']);self.progress['value']=0
        self.cancel_requested=False
        self.future=self.pool.submit(work);self.done=done

    def progress_event(self,current,total):self.events.put((current,total))

    def process_video(self):
        if not self.path:self.status.set('Importez d’abord une vidéo locale.');return
        if self.future is not None:return
        try:settings=self.current_settings();settings.validate()
        except (ValueError,tk.TclError) as error:self.status.set(str(error));return
        self.pause();self.status.set('Conversion en cours.')
        engine=VideoEngine(self.ffmpeg)
        self.start_job(lambda:engine.decode(self.path,settings,self.progress_event),self.accept_clip,engine)

    def poll(self):
        if self.closed:return
        latest=None
        try:
            while True:latest=self.events.get_nowait()
        except Empty:pass
        if latest:
            current,total=latest;self.progress['value']=min(100,current/max(1,total)*100)
        if self.future is not None and self.future.done():
            future=self.future;done=self.done;self.future=None;self.engine=None
            self.convert_button.state(['!disabled'])
            try:
                if self.cancel_requested:raise Cancelled()
                done(future.result());self.progress['value']=100
            except Cancelled:self.status.set('Traitement annulé. L’aperçu précédent est conservé.')
            except Exception as error:self.status.set(str(error))
        self.root.after(40,self.poll)

    def accept_clip(self,clip):
        self.frame_undo=None
        self.pause();self.clip=clip;self.photos.clear();self.index=0
        self.timeline.configure(to=max(0,len(clip.frames)-1));self.set_index(0)
        speed=f', traité en {clip.processing_seconds:.2f} s ({len(clip.frames)/clip.processing_seconds:.0f} images/s)' if clip.processing_seconds else ''
        self.status.set(f'{len(clip.frames)} images, {clip.width} × {clip.height}, {clip.memory_bytes/1048576:.2f} Mo{speed}')

    def set_index(self,index):
        if not self.clip:return
        self.index=max(0,min(len(self.clip.frames)-1,int(index)))
        self.scrubbing=True;self.seek.set(self.index);self.scrubbing=False;self.draw()

    def scrub(self,value):
        if self.clip and not self.scrubbing:
            self.pause();self.index=max(0,min(len(self.clip.frames)-1,round(float(value))));self.draw()

    def draw(self):
        if not self.clip:return
        clip=self.clip;scale=max(.1,min((self.canvas.winfo_width()-24)/clip.width,(self.canvas.winfo_height()-24)/clip.height))
        size=(max(1,round(clip.width*scale)),max(1,round(clip.height*scale)))
        key=(self.index,size);photo=self.photos.get(key)
        if photo is None:
            photo=ImageTk.PhotoImage(clip.image(self.index).resize(size,Image.Resampling.NEAREST))
            self.photos[key]=photo
            while len(self.photos)>8:self.photos.popitem(last=False)
        self.photo=photo;self.canvas.itemconfigure(self.item,image=photo)
        self.canvas.coords(self.item,self.canvas.winfo_width()/2,self.canvas.winfo_height()/2)
        self.position.set(f'{self.index/clip.fps:06.2f} s / {clip.duration:06.2f} s  {self.index+1}/{len(clip.frames)}')

    def toggle_play(self):
        if self.playing:self.pause();return
        if not self.clip:return
        self.playing=True;self.play_button.configure(text='Pause')
        self.play_start=time.monotonic()-self.index/self.clip.fps;self.tick()

    def tick(self):
        self.play_job=None
        if not self.playing or self.closed or not self.clip:return
        index=int((time.monotonic()-self.play_start)*self.clip.fps)%len(self.clip.frames)
        self.set_index(index);self.play_job=self.root.after(max(10,round(1000/self.clip.fps)),self.tick)

    def pause(self):
        self.playing=False;self.play_button.configure(text='Lire')
        if self.play_job:self.root.after_cancel(self.play_job);self.play_job=None

    def cancel(self):
        if self.future is not None:
            self.cancel_requested=True
            if self.engine:self.engine.cancel()
            else:self.future.cancel()
            self.status.set('Annulation demandée.')

    def export_packed(self):
        if not self.clip or self.future is not None:return
        path=filedialog.asksaveasfilename(defaultextension='.nandvideo',filetypes=[('Vidéo Nand 1 bit','*.nandvideo')])
        if path:
            clip=self.clip;self.start_job(lambda:save_clip(path,clip),lambda _:self.status.set('Séquence 1 bit enregistrée.'))

    def export_movie(self,suffix):
        if not self.clip or self.future is not None:return
        path=filedialog.asksaveasfilename(defaultextension=suffix,filetypes=[('Vidéo '+suffix,'*'+suffix)])
        if path:
            engine=VideoEngine(self.ffmpeg);clip=self.clip
            self.start_job(lambda:engine.export_movie(clip,path,self.progress_event),lambda _:self.status.set('Vidéo exportée : '+Path(path).name),engine)

    def frames_ready(self):
        if self.future is not None:
            self.status.set('Attendez la fin du traitement avant de modifier les frames.');return False
        self.pause();return True

    def add_frames(self):
        if not self.frames_ready():return
        paths=filedialog.askopenfilenames(title='Ajouter des images après la frame sélectionnée',filetypes=IMAGE_TYPES)
        if not paths:return
        previous=self.clip;index=self.index
        try:
            options=self.current_settings();options.validate()
            size=(previous.width,previous.height) if previous else (options.width,options.width//2)
            limit=MAX_FRAMES-(len(previous.frames) if previous else 0)
            if len(paths)>limit:raise ValueError(f'La vidéo accepte {MAX_FRAMES} frames maximum.')
            settings=Settings(threshold=options.threshold,contrast=options.contrast,invert=options.invert,
                dither='Bayer 4 × 4' if options.dither=='Bayer 4 × 4' else 'Seuil')
        except (ValueError,tk.TclError) as error:self.status.set(str(error));return
        def work():
            _,images=read_frames(paths,size,settings,limit,opaque=True)
            packed=tuple(image.convert('1').tobytes() for image in images)
            at=index+1 if previous else 0
            clip=replace(previous,frames=previous.frames[:at]+packed+previous.frames[at:],processing_seconds=0) if previous else VideoClip(*size,float(options.fps),packed,'Images importées')
            return clip,at
        def done(data):
            clip,at=data
            self.replace_frames(clip,at,f'{len(paths)} frame(s) ajoutée(s). Export et test CPU utilisent la séquence modifiée.')
        self.start_job(work,done)

    def replace_frames(self,clip,index,message):
        saved=(self.clip,self.index)
        machine=self.app.machine
        if isinstance(machine,VideoCPU) and machine.clip is self.clip:self.app.pause_machine()
        self.accept_clip(clip);self.set_index(index);self.frame_undo=saved
        self.status.set(message)

    def delete_frame(self):
        if not self.frames_ready() or not self.clip:return
        if len(self.clip.frames)==1:
            self.status.set('Conservez au moins une frame : ajoutez une image avant de supprimer celle-ci.');return
        index=self.index
        clip=replace(self.clip,frames=self.clip.frames[:index]+self.clip.frames[index+1:],processing_seconds=0)
        self.replace_frames(clip,min(index,len(clip.frames)-1),'Frame supprimée. Annuler frames permet de la récupérer.')

    def undo_frames(self):
        if not self.frames_ready():return
        saved=getattr(self,'frame_undo',None)
        if not saved or saved[0] is None:
            self.status.set('Aucune modification de frames à annuler.');return
        clip,index=saved
        self.replace_frames(clip,index,'Modification de frames annulée.');self.frame_undo=None

    def test_cpu(self):
        if not self.clip:
            self.status.set('Traitez ou ouvrez une vidéo .nandvideo avant de la tester sur CPU.');return
        self.pause();self.app.running=False;self.app.keys.clear()
        self.app.machine=VideoCPU(self.clip,self.index)
        self.app.loaded_kind='video';self.app.loaded_path=None
        self.app.speed.set('Rapide');self.app.tabs.select(self.app.emu)
        self.app.status.set('Vidéo CPU : images fournies par le Studio en RAM, dessin exécuté par Hack. Pause, pas à pas et réinitialisation disponibles.')
        self.app.draw_machine();self.app.run_machine()

    def send_frame(self):
        if not self.clip:return
        image=self.clip.image(self.index).convert('RGBA')
        settings=Settings(mode='Écran 512 × 256' if image.size==(512,256) else 'Sprite')
        self.app.accept_artwork(([image],[image.copy()],image.copy(),settings,'VideoFrame'),Path('video-frame.png'))
        self.app.tabs.select(self.app.work)

    def send_sequence(self):
        if not self.clip:return
        count=len(self.clip.frames)
        clip=self.clip
        start=self.index
        transfer_count=min(count,256)
        def work():
            frames=[clip.image((start+i)%count).convert('RGBA') for i in range(transfer_count)]
            source,settings=source_sheet(frames,Settings())
            return frames,[im.copy() for im in frames],source,settings,'VideoFrames'
        def done(data):
            self.app.accept_artwork(data,Path('video-sequence.png'))
            self.app.fps.set(round(clip.fps));self.app.tabs.select(self.app.work)
            message=f'{transfer_count} frames envoyées à l’atelier.'
            if count>transfer_count:message+=' Les frames commencent à la position sélectionnée.'
            self.app.status.set(message);self.status.set(message)
        self.start_job(work,done)

    def close(self):
        self.closed=True;self.pause();self.cancel();self.pool.shutdown(wait=False,cancel_futures=True)
