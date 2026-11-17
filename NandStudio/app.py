"""Nand Asset Studio — a local image workshop with VM and Hack CPU playgrounds."""
from pathlib import Path
import json
import tempfile
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser
from concurrent.futures import ThreadPoolExecutor
from collections import OrderedDict
from PIL import Image, ImageTk, ImageDraw, ImageOps
from jobs import LatestWorker
from ui_features import StudioFeatures
from artwork_ui import ArtworkActions
from video_ui import VideoTab
from core import Settings, convert, screen_image, jack_screen, jack_asset, asm_screen, export_project, zip_project
from machines import HackCPU, VM, assemble, framebuffer
from video_cpu import VideoCPU
from compiler import compile_jack

ROOT=Path(__file__).resolve().parent
BG='#10131e';PANEL='#191e2c';CARD='#222a3b';TEXT='#eef2ff';MUTED='#94a0b8';ACCENT='#a89bff';CYAN='#65e1ce'


class Studio(ArtworkActions,StudioFeatures):
    def __init__(self,root):
        self.root=root;root.title('Nand Asset Studio');root.geometry('1280x880');root.minsize(1000,700)
        root.configure(bg=BG)
        self.source=None;self.source_path=None;self.frames=[];self.index=0;self.machine=None
        self.base_frames=[];self.edit_overrides={}
        self.running=False;self.playing=False;self.loaded_path=None;self.loaded_kind=None
        self.preview_photo=None;self.machine_photo=None;self.convert_job=None
        self.pool=ThreadPoolExecutor(max_workers=1);self.future=None;self.temp=tempfile.TemporaryDirectory(prefix='nandstudio-')
        self.keys={};self.closed=False
        self.convert_worker=LatestWorker();self.code_worker=LatestWorker()
        self.converting=False;self.generation=0;self.accepted_settings=None;self.accepted_source=None
        self.preview_cache=OrderedDict();self.code_cache=OrderedDict();self.thumb_cache=OrderedDict()
        self.animation_job=None;self.code_job=None;self.last_video=None;self.last_display_size=None
        self.last_paint=0;self.last_status=0;self.source_view=tk.StringVar(value='Résultat')
        self.zoom=tk.StringVar(value='Ajuster');self.fps=tk.IntVar(value=8)
        self.vars={}
        for key,value in Settings().__dict__.items():
            if key=='background': continue
            cls=tk.BooleanVar if isinstance(value,bool) else tk.IntVar if isinstance(value,int) else tk.DoubleVar if isinstance(value,float) else tk.StringVar
            self.vars[key]=cls(value=value)
        self.background=(255,255,255)
        self.class_name=tk.StringVar(value='Artwork');self.frame_label=tk.StringVar(value='Image 1 / 1')
        self.status=tk.StringVar(value='Prêt. Importez une image ou ouvrez un exemple.')
        self.stats=tk.StringVar(value='512 × 256 pixels  /  1 bit  /  16 Ko vidéo')
        self.emu_status=tk.StringVar(value='Aucun programme chargé')
        self.speed=tk.StringVar(value='Normal');self.kind=tk.StringVar(value='Jack')
        self.entry=tk.StringVar(value='')
        self.setup_styles();self.build()
        for value in self.vars.values(): value.trace_add('write',lambda *_:self.schedule_convert())
        self.root.protocol('WM_DELETE_WINDOW',self.close)
        self.root.after(16,self.machine_tick)
        self.root.after(30,self.poll_workers)
        self.root.bind('<FocusOut>',self.focus_out)
        self.root.bind('<KeyPress>',self.key_down);self.root.bind('<KeyRelease>',self.key_up)
        self.root.bind('<Control-o>',lambda e:self.open_current())
        self.root.bind('<Control-e>',lambda e:self.export_current())
        self.root.bind('<Control-s>',lambda e:self.save_current())
        self.class_name.trace_add('write',lambda *_:self.schedule_code())
        example=ROOT/'examples'/'grotte.png'
        if example.exists(): self.load_image(example)

    def setup_styles(self):
        s=ttk.Style();s.theme_use('clam')
        s.configure('.',font=('Segoe UI',10),background=BG,foreground=TEXT)
        s.configure('TFrame',background=BG);s.configure('Panel.TFrame',background=PANEL)
        s.configure('TLabel',background=BG,foreground=TEXT)
        s.configure('TButton',background=CARD,foreground=TEXT,padding=(12,8),borderwidth=0)
        s.map('TButton',background=[('active','#35415d'),('disabled',PANEL)],foreground=[('disabled',MUTED)])
        s.configure('Accent.TButton',background=ACCENT,foreground='#171328',font=('Segoe UI',10,'bold'))
        s.map('Accent.TButton',background=[('active','#c1b7ff')])
        s.configure('TNotebook',background=BG,borderwidth=0)
        s.configure('TNotebook.Tab',background=BG,foreground=MUTED,padding=(22,12))
        s.map('TNotebook.Tab',background=[('selected',PANEL)],foreground=[('selected',CYAN)])
        s.configure('TCheckbutton',background=PANEL,foreground=TEXT)
        s.map('TCheckbutton',background=[('active',PANEL)])
        s.configure('TCombobox',fieldbackground=CARD,background=CARD,foreground=TEXT,arrowcolor=TEXT)
        s.map('TCombobox',fieldbackground=[('readonly',CARD)],selectbackground=[('readonly',CARD)],selectforeground=[('readonly',TEXT)])
        s.configure('TEntry',fieldbackground=CARD,foreground=TEXT,insertcolor=TEXT,padding=5)
        s.configure('TScale',background=PANEL,troughcolor=CARD)
        s.configure('TSpinbox',fieldbackground=CARD,foreground=TEXT,arrowcolor=TEXT)

    def label(self,parent,text,size=10,color=TEXT,bold=False,bg=None):
        w=tk.Label(parent,text=text,font=('Segoe UI',size,'bold' if bold else 'normal'),fg=color,bg=bg or parent.cget('bg') if isinstance(parent,tk.Frame) else BG,anchor='w')
        return w

    def build(self):
        header=tk.Frame(self.root,bg=BG);header.pack(fill='x',padx=28,pady=(16,8))
        self.label(header,'Nand Asset Studio',24,TEXT,True).pack(side='left')
        ttk.Button(header,text='Exporter (Ctrl+E)',command=self.export_current,style='Accent.TButton').pack(side='right',padx=(8,0))
        ttk.Button(header,text='Ouvrir (Ctrl+O)',command=self.open_current).pack(side='right')
        ttk.Button(header,text='Disposition',command=self.reset_layout).pack(side='right',padx=6)
        self.label(self.root,'Images, sprites, vidéo et exécution Hack.',10,MUTED).pack(anchor='w',padx=30,pady=(0,10))
        self.tabs=ttk.Notebook(self.root);self.tabs.pack(fill='both',expand=True,padx=24)
        self.work=tk.Frame(self.tabs,bg=PANEL);self.emu=tk.Frame(self.tabs,bg=PANEL);self.guide=tk.Frame(self.tabs,bg=PANEL)
        self.video_panel=tk.Frame(self.tabs,bg=PANEL)
        self.tabs.add(self.work,text='01   Atelier');self.tabs.add(self.video_panel,text='02   Vidéo')
        self.tabs.add(self.emu,text='03   Exécuteur');self.tabs.add(self.guide,text='04   Guide')
        self.build_work();self.build_emulator();self.build_guide()
        self.video=VideoTab(self,self.video_panel)
        footer=tk.Frame(self.root,bg=BG);footer.pack(fill='x',padx=28,pady=12)
        self.progress=ttk.Progressbar(footer,mode='indeterminate',length=70)
        self.progress.pack(side='left',padx=(0,12))
        tk.Label(footer,textvariable=self.status,bg=BG,fg=MUTED,font=('Segoe UI',9),anchor='w',width=85).pack(side='left',fill='x',expand=True)
        self.label(footer,'Nand2Tetris  512 × 256',9,CYAN).pack(side='right')

    def section(self,parent,text):
        self.label(parent,text,10,CYAN,True).pack(anchor='w',pady=(14,7))

    def combo(self,parent,key,values):
        c=ttk.Combobox(parent,textvariable=self.vars[key],values=values,state='readonly');c.pack(fill='x',pady=3)
        return c

    def build_work(self):
        self.work_split=tk.PanedWindow(self.work,orient='horizontal',bg=CARD,sashwidth=9,showhandle=True,bd=0)
        self.work_split.pack(fill='both',expand=True,padx=12,pady=12)
        sidebar=tk.Frame(self.work_split,bg=PANEL,padx=6)
        self.work_split.add(sidebar,minsize=240,width=310,stretch='never')
        export_card=tk.Frame(sidebar,bg=CARD,padx=12,pady=10)
        export_card.pack(side='bottom',fill='x',pady=(10,0))
        self.label(export_card,'EXPORT',9,CYAN,True).pack(anchor='w',pady=(0,5))
        ttk.Entry(export_card,textvariable=self.class_name).pack(fill='x')
        self.export_button=ttk.Button(export_card,text='Exporter le projet + ZIP',command=self.export,style='Accent.TButton')
        self.export_button.pack(fill='x',pady=(7,0))
        scroll=tk.Canvas(sidebar,bg=PANEL,width=280,highlightthickness=0)
        scrollbar=ttk.Scrollbar(sidebar,orient='vertical',command=scroll.yview)
        scrollbar.pack(side='right',fill='y');scroll.pack(side='left',fill='both',expand=True)
        scroll.configure(yscrollcommand=scrollbar.set)
        left=tk.Frame(scroll,bg=PANEL)
        item=scroll.create_window((0,0),window=left,anchor='nw',width=280)
        left.bind('<Configure>',lambda e:scroll.configure(scrollregion=scroll.bbox('all')))
        scroll.bind('<Configure>',lambda e:scroll.itemconfigure(item,width=e.width))
        def wheel(event):
            widget=event.widget
            while widget is not None:
                if widget==left:
                    scroll.yview_scroll(-1 if event.delta>0 else 1,'units')
                    return 'break'
                widget=getattr(widget,'master',None)
        self.root.bind('<MouseWheel>',wheel,add='+')
        ttk.Button(left,text='Importer une image',command=self.open_image,style='Accent.TButton').pack(fill='x')
        ttk.Button(left,text='Ouvrir un artwork',command=self.open_artwork_project).pack(fill='x',pady=(5,0))
        self.filename=self.label(left,'PNG, JPG, GIF, BMP, WEBP',9,MUTED);self.filename.pack(anchor='w',pady=7)
        examples=tk.Frame(left,bg=PANEL);examples.pack(fill='x')
        ttk.Button(examples,text='Paysage',command=self.scene_example).pack(side='left',expand=True,fill='x',padx=(0,4))
        ttk.Button(examples,text='Sprites',command=self.sprite_example).pack(side='left',expand=True,fill='x')
        self.section(left,'TYPE D’ASSET')
        self.combo(left,'mode',['Écran 512 × 256','Sprite','Planche de sprites'])
        self.fit_control=self.combo(left,'fit',['Contenir','Remplir','Étirer'])
        self.section(left,'NOIR & BLANC')
        self.combo(left,'dither',['Seuil','Floyd–Steinberg','Bayer 4 × 4'])
        for key,label,lo,hi in [('threshold','Seuil',0,255),('contrast','Contraste',0.2,3.0)]:
            row=tk.Frame(left,bg=PANEL);row.pack(fill='x',pady=(7,0))
            self.label(row,label,9,MUTED).pack(side='left')
            tk.Label(row,textvariable=self.vars[key],bg=PANEL,fg=TEXT,width=6,anchor='e').pack(side='right')
            # Rounded values avoid IntVar errors and excessively long contrast labels.
            value=tk.DoubleVar(value=self.vars[key].get())
            ttk.Scale(left,from_=lo,to=hi,variable=value,command=lambda v,k=key:self.vars[k].set(round(float(v)) if k=='threshold' else round(float(v),2))).pack(fill='x')
        ttk.Checkbutton(left,text='Inverser noir / blanc',variable=self.vars['invert']).pack(anchor='w',pady=4)
        self.section(left,'SPRITES & TRANSPARENCE')
        row=tk.Frame(left,bg=PANEL);row.pack(fill='x')
        self.sprite_dimensions=row
        self.dimension_controls={}
        for key,label in [('cell_width','Largeur'),('cell_height','Hauteur'),('scale','Échelle')]:
            box=tk.Frame(row,bg=PANEL);box.pack(side='left',expand=True,fill='x',padx=2)
            self.label(box,label,8,MUTED).pack(anchor='w')
            control=ttk.Spinbox(box,from_=1,to=512 if key!='scale' else 8,textvariable=self.vars[key],width=6)
            control.pack(fill='x');self.dimension_controls[key]=control
        ttk.Checkbutton(left,text='Retirer la couleur de fond',variable=self.vars['remove_background']).pack(anchor='w',pady=(8,2))
        ttk.Checkbutton(left,text='Retirer un damier (2 couleurs dominantes)',variable=self.vars['remove_checker']).pack(anchor='w',pady=2)
        ttk.Button(left,text='Choisir la couleur de fond',command=self.pick_color).pack(fill='x',pady=3)
        row=tk.Frame(left,bg=PANEL);row.pack(fill='x')
        self.label(row,'Tolérance',9,MUTED).pack(side='left')
        ttk.Spinbox(row,from_=0,to=255,textvariable=self.vars['tolerance'],width=6).pack(side='right')
        presets=tk.Frame(left,bg=PANEL);presets.pack(fill='x',pady=(12,0))
        ttk.Button(presets,text='Sauver réglages',command=self.save_preset).pack(side='left',expand=True,fill='x',padx=(0,4))
        ttk.Button(presets,text='Charger',command=self.load_preset).pack(side='left')
        right=tk.Frame(self.work_split,bg=PANEL,padx=10,pady=6)
        self.work_split.add(right,minsize=470,stretch='always')
        self.canvas_code_split=tk.PanedWindow(right,orient='vertical',bg=CARD,sashwidth=9,showhandle=True,bd=0)
        self.canvas_code_split.pack(fill='both',expand=True)
        preview_panel=tk.Frame(self.canvas_code_split,bg=PANEL)
        self.canvas_code_split.add(preview_panel,minsize=230,stretch='always')
        code_panel=tk.Frame(self.canvas_code_split,bg=PANEL)
        self.canvas_code_split.add(code_panel,minsize=85,height=170,stretch='never')
        top=tk.Frame(preview_panel,bg=PANEL);top.pack(fill='x')
        self.label(top,'APERÇU',10,CYAN,True).pack(side='left')
        ttk.Button(top,text='Tester sur CPU Hack',command=self.test_asset).pack(side='right')
        ttk.Button(top,text='Retoucher',command=self.open_editor,style='Accent.TButton').pack(side='right',padx=6)
        views=tk.Frame(preview_panel,bg=PANEL);views.pack(fill='x',pady=(10,0))
        self.view_buttons={}
        for view in ('Résultat','Original','Comparer'):
            button=ttk.Button(views,text=view,command=lambda v=view:self.set_view(v),style='Accent.TButton' if view=='Résultat' else 'TButton')
            button.pack(side='left',padx=(0,4));self.view_buttons[view]=button
        zoom=ttk.Combobox(views,textvariable=self.zoom,values=['Ajuster','100 %','200 %','400 %'],state='readonly',width=9)
        zoom.pack(side='right');zoom.bind('<<ComboboxSelected>>',lambda e:self.draw_preview())
        holder=tk.Frame(preview_panel,bg=BG);holder.pack(fill='both',expand=True,pady=(8,8))
        holder.grid_rowconfigure(0,weight=1);holder.grid_columnconfigure(0,weight=1)
        self.preview=tk.Canvas(holder,bg='#090c13',highlightthickness=1,highlightbackground=CARD,height=300)
        self.preview.grid(row=0,column=0,sticky='nsew');self.preview.bind('<Configure>',lambda e:self.draw_preview())
        xs=ttk.Scrollbar(holder,orient='horizontal',command=self.preview.xview);xs.grid(row=1,column=0,sticky='ew')
        ys=ttk.Scrollbar(holder,orient='vertical',command=self.preview.yview);ys.grid(row=0,column=1,sticky='ns')
        self.preview.configure(xscrollcommand=xs.set,yscrollcommand=ys.set)
        self.preview_item=self.preview.create_image(0,0,anchor='nw')
        controls=tk.Frame(preview_panel,bg=PANEL);controls.pack(fill='x')
        self.frame_controls=controls
        ttk.Button(controls,text='Précédente',command=lambda:self.change_frame(-1)).pack(side='left')
        self.play_button=ttk.Button(controls,text='Lire',command=self.toggle_animation)
        self.play_button.pack(side='left',padx=5)
        ttk.Button(controls,text='Suivante',command=lambda:self.change_frame(1)).pack(side='left')
        tk.Label(controls,textvariable=self.frame_label,bg=PANEL,fg=MUTED).pack(side='left',padx=12)
        ttk.Spinbox(controls,from_=1,to=30,textvariable=self.fps,width=4).pack(side='right')
        self.label(controls,'images/s',9,MUTED).pack(side='right',padx=6)
        frame_actions=tk.Frame(preview_panel,bg=PANEL);frame_actions.pack(fill='x',pady=(7,0))
        for text,command in [('Ajouter des frames',self.add_frames),('Supprimer la frame',self.delete_frame),('Annuler les frames',self.undo_frames)]:
            ttk.Button(frame_actions,text=text,command=command).pack(side='left',padx=(0,5))
        self.filmstrip=tk.Canvas(preview_panel,bg=BG,height=64,highlightthickness=0)
        self.filmstrip.pack(fill='x',pady=(8,0))
        self.filmstrip.bind('<Button-1>',self.select_thumbnail)
        self.filmstrip.bind('<Configure>',lambda e:self.draw_filmstrip())
        tk.Label(preview_panel,textvariable=self.stats,bg=PANEL,fg=MUTED,anchor='w').pack(fill='x',pady=8)
        codebar=tk.Frame(code_panel,bg=PANEL);codebar.pack(fill='x')
        self.label(codebar,'CODE',9,CYAN,True).pack(side='left')
        ttk.Button(codebar,text='Copier',command=self.copy_code).pack(side='left',padx=10)
        ttk.Button(codebar,text='Sauver artwork',command=self.save_artwork_project).pack(side='left')
        for kind in ('Jack','ASM','JSON'):
            ttk.Button(codebar,text=kind,command=lambda k=kind:self.show_code(k)).pack(side='right',padx=2)
        code_holder=tk.Frame(code_panel,bg=BG);code_holder.pack(fill='both',expand=True,pady=(7,0))
        self.code=tk.Text(code_holder,height=8,bg=BG,fg='#b9d7d2',insertbackground=TEXT,relief='flat',font=('Consolas',9),wrap='none',padx=10,pady=8)
        self.code.pack(side='left',fill='both',expand=True);self.code.configure(state='disabled')
        code_scroll=ttk.Scrollbar(code_holder,orient='vertical',command=self.code.yview)
        code_scroll.pack(side='right',fill='y');self.code.configure(yscrollcommand=code_scroll.set)

    def build_emulator(self):
        toolbar=tk.Frame(self.emu,bg=PANEL);toolbar.pack(fill='x',padx=18,pady=14)
        for text,cmd in [('Ouvrir ASM / HACK',self.open_cpu),('Dossier VM',self.open_vm),('Compiler Jack',self.open_jack)]:
            ttk.Button(toolbar,text=text,command=cmd).pack(side='left',padx=(0,7))
        ttk.Combobox(toolbar,textvariable=self.speed,values=['Lent','Normal','Rapide'],state='readonly',width=9).pack(side='right')
        actions=tk.Frame(self.emu,bg=PANEL);actions.pack(fill='x',padx=18)
        for text,cmd in [('Exécuter',self.run_machine),('Pause',self.pause_machine),('Réinitialiser',self.reset_machine),('Pas à pas',self.single_step)]:
            ttk.Button(actions,text=text,command=cmd,style='Accent.TButton' if text=='Exécuter' else 'TButton').pack(side='left',padx=(0,7))
        self.capture=tk.BooleanVar(value=False)
        ttk.Checkbutton(actions,text='Capturer le clavier',variable=self.capture,command=self.capture_changed).pack(side='right')
        self.emu_split=tk.PanedWindow(self.emu,orient='vertical',bg=CARD,sashwidth=9,showhandle=True,bd=0)
        self.emu_split.pack(fill='both',expand=True,padx=18,pady=14)
        screen_panel=tk.Frame(self.emu_split,bg=PANEL)
        diagnostics=tk.Frame(self.emu_split,bg=PANEL)
        self.emu_split.add(screen_panel,minsize=160,stretch='always')
        self.emu_split.add(diagnostics,minsize=75,height=100,stretch='never')
        self.display=tk.Canvas(screen_panel,bg='#080b12',height=420,highlightthickness=1,highlightbackground=CARD,takefocus=True)
        self.display.pack(fill='both',expand=True)
        self.display.bind('<Configure>',lambda e:self.draw_machine())
        self.display.bind('<Button-1>',lambda e:(self.capture.set(True),self.display.focus_set()))
        tk.Label(diagnostics,textvariable=self.emu_status,bg=PANEL,fg=CYAN,font=('Consolas',10),anchor='w').pack(fill='x',padx=10,pady=5)
        self.label(diagnostics,'Cliquez sur l’écran pour le clavier. Entrée, flèches, Espace, lettres. Échap libère la capture.',10,MUTED).pack(anchor='w',padx=10,pady=4)
        self.label(diagnostics,'VM pédagogique : système natif Python, police approximative. CPU : ALU, RAM, ROM et clavier Hack.',9,MUTED).pack(anchor='w',padx=10,pady=(0,10))

    def build_guide(self):
        body=tk.Text(self.guide,bg=PANEL,fg=TEXT,font=('Segoe UI',12),wrap='word',relief='flat',padx=32,pady=24)
        body.pack(fill='both',expand=True)
        body.insert('1.0','''AIDE\n\nAtelier\nImportez une image, choisissez le mode de conversion, puis exportez le projet. Retoucher ouvre l’éditeur de pixels. Les séparateurs entre les panneaux sont redimensionnables.\n\nFrames\nAjoutez, supprimez ou annulez les modifications de frames sous l’aperçu. L’artwork .nandart conserve les frames et les retouches.\n\nExécuteur\nTester sur CPU Hack affiche l’image courante. Vous pouvez aussi ouvrir un programme ASM/HACK, charger un dossier VM ou compiler des sources Jack.\n\nVidéo\nImportez un fichier local, choisissez l’extrait et traitez-le avec FFmpeg. Les exports MP4, GIF et .nandvideo restent locaux. Le test CPU lit les frames depuis le Studio.\n''')
        body.configure(state='disabled')

    def current_settings(self):
        return Settings(**{key:var.get() for key,var in self.vars.items()},background=self.background)

    def open_current(self):
        if self.tabs.select()==str(self.video_panel):self.video.open_video()
        else:self.open_image()

    def export_current(self):
        if self.tabs.select()==str(self.video_panel):self.video.export_packed()
        else:self.export()

    def save_current(self):
        if self.tabs.select()==str(self.video_panel):self.video.export_packed()
        else:self.save_artwork_project()

    def reset_layout(self):
        self.work_split.sash_place(0,310,0)
        self.canvas_code_split.sash_place(0,0,max(230,self.canvas_code_split.winfo_height()-180))
        self.emu_split.sash_place(0,0,max(160,self.emu_split.winfo_height()-110))
        self.video.split.sash_place(0,320,0)
        self.status.set('Disposition réinitialisée. Glissez les séparateurs pour ajuster les panneaux.')

    def copy_code(self):
        if getattr(self,'current_code',None):
            self.root.clipboard_clear();self.root.clipboard_append(self.current_code)
            self.status.set('Code complet copié.')

    def open_image(self):
        path=filedialog.askopenfilename(title='Importer une image',filetypes=[('Images','*.png *.jpg *.jpeg *.gif *.bmp *.webp'),('Tous les fichiers','*.*')])
        if path:self.load_image(path)

    def load_image(self,path):
        self.frame_undo=None
        try:
            with Image.open(path) as im:
                if im.width*im.height>40_000_000: raise ValueError('Image trop grande : limitez-la à 40 mégapixels.')
                self.source=im.convert('RGBA')
            self.edit_overrides={}
            self.source_path=Path(path);self.filename.configure(text=f'{Path(path).name[:31]} ({self.source.width} × {self.source.height})')
            self.index=0;self.reconvert()
        except Exception as error:self.error(error)

    def sprite_example(self):
        self.vars['mode'].set('Planche de sprites');self.vars['cell_width'].set(32);self.vars['cell_height'].set(32)
        self.vars['remove_checker'].set(False);self.vars['remove_background'].set(False)
        self.load_image(ROOT/'examples/sprites.png')

    def scene_example(self):
        self.vars['mode'].set('Écran 512 × 256')
        self.vars['remove_checker'].set(False);self.vars['remove_background'].set(False)
        self.load_image(ROOT/'examples/grotte.png')

    def pick_color(self):
        color=colorchooser.askcolor(color='#%02x%02x%02x'%self.background,title='Couleur à rendre transparente')[0]
        if color:
            self.background=tuple(map(int,color));self.vars['remove_background'].set(True);self.schedule_convert()

    def background_job(self,job,done):
        if self.future is not None:self.status.set('Une opération est déjà en cours.');return
        self.status.set('Traitement en cours.');self.progress.start(12);self.future=self.pool.submit(job)
        future=self.future
        def poll():
            if self.closed:return
            if not future.done():self.root.after(50,poll);return
            self.future=None
            try:done(future.result())
            except Exception as error:self.error(error)
        self.root.after(100,poll)

    def export(self):
        if not self.frames:return
        if self.converting or self.convert_job:self.status.set('Attendez la fin de la conversion avant d’exporter.');return
        parent=filedialog.askdirectory(title='Dossier parent pour le nouveau projet')
        if not parent:return
        try:settings=self.accepted_settings;name=self.class_name.get();frames=list(self.frames)
        except Exception as error:self.error(error);return
        dest=Path(parent)/(name+'-'+time.strftime('%Y%m%d-%H%M%S'))
        source=self.source_path
        def job():
            folder,warning=export_project(dest,source,settings,frames,name);archive=dest.with_suffix('.zip');zip_project(folder,archive)
            return folder,archive,warning
        def done(result):
            folder,archive,warning=result;self.status.set('Export terminé : '+str(archive))
            messagebox.showinfo('Projet exporté',f'Projet : {folder}\nZIP : {archive}\n\n'+(warning or 'Jack, VM, ASM, HACK et images prêts.'))
        self.background_job(job,done)

    def test_asset(self):
        if not self.frames:return
        if self.converting or self.convert_job:self.status.set('Attendez la fin de la conversion.');return
        try:
            asm=asm_screen(self.frames[self.index]);rom=assemble(asm)
            path=Path(self.temp.name)/'asset.asm';path.write_text(asm)
            self.loaded_path=path;self.loaded_kind='cpu';self.machine=HackCPU(rom)
            self.tabs.select(self.emu);self.run_machine()
        except Exception as error:self.error(error)

    def open_cpu(self):
        path=filedialog.askopenfilename(filetypes=[('Hack / Assembleur','*.hack *.asm')])
        if path:
            self.loaded_path=Path(path);self.loaded_kind='cpu';self.reset_machine()

    def open_vm(self):
        folder=filedialog.askdirectory(title='Dossier des classes VM')
        if folder:
            self.loaded_path=Path(folder);self.loaded_kind='vm';self.reset_machine()

    def open_jack(self):
        folder=filedialog.askdirectory(title='Dossier des classes Jack à compiler')
        if not folder:return
        paths=list(Path(folder).glob('*.jack'))
        if not paths:self.error('Aucune classe .jack dans ce dossier.');return
        dest=Path(self.temp.name)/('compiled-'+time.strftime('%H%M%S'));dest.mkdir(exist_ok=True)
        def job():
            for path in paths:compile_jack(path,dest/(path.stem+'.vm'))
            for path in (ROOT/'vendor/os').glob('*.vm'):(dest/path.name).write_bytes(path.read_bytes())
            return dest
        def done(path):
            self.loaded_path=path;self.loaded_kind='vm';self.reset_machine();self.status.set('Jack compilé dans un dossier temporaire.')
        self.background_job(job,done)

    def reset_machine(self):
        self.running=False;self.keys.clear()
        if self.loaded_kind=='video' and isinstance(self.machine,VideoCPU):
            self.machine=VideoCPU(self.machine.clip,self.machine.start)
            self.draw_machine();return
        if not self.loaded_path:return
        try:
            path=self.loaded_path
            if self.loaded_kind=='vm':self.machine=VM(path.glob('*.vm'))
            else:
                text=path.read_text(encoding='utf-8-sig')
                if path.suffix.lower()=='.hack':
                    rows=[line.strip() for line in text.splitlines() if line.strip()]
                    if any(len(line)!=16 or set(line)-{'0','1'} for line in rows):raise ValueError('Chaque ligne .hack doit contenir 16 bits.')
                    rom=[int(line,2) for line in rows]
                else:rom=assemble(text)
                self.machine=HackCPU(rom)
            self.draw_machine();self.status.set('Programme chargé : '+str(path.name))
        except Exception as error:self.machine=None;self.error(error)

    def run_machine(self):
        if self.machine and not self.machine.halted:self.running=True;self.display.focus_set()

    def pause_machine(self):
        self.running=False;self.draw_machine()

    def single_step(self):
        self.running=False
        if not self.machine:return
        try:self.machine.step();self.draw_machine()
        except Exception as error:self.error(error)

    def machine_tick(self):
        if self.closed:return
        started=time.perf_counter()
        if self.running and self.machine:
            try:
                budget={'Lent':1000,'Normal':15000,'Rapide':60000}[self.speed.get()]
                # CPU work yields after a bounded slice so keyboard/settings remain reactive.
                self.machine.run(budget,max_seconds=.008)
                if self.machine.halted:self.running=False
                now=time.perf_counter()
                if now-self.last_paint>=1/30:
                    if self.tabs.select()==str(self.emu):self.draw_machine()
                    self.last_paint=now
            except Exception as error:self.running=False;self.error(error)
        elapsed=(time.perf_counter()-started)*1000
        self.root.after(max(1,round(16-elapsed)),self.machine_tick)

    def draw_machine(self):
        if not self.machine:return
        m=self.machine
        scale=max(.1,min((self.display.winfo_width()-24)/512,(self.display.winfo_height()-24)/256))
        size=(max(1,int(512*scale)),max(1,int(256*scale)))
        video=tuple(m.ram[16384:24576]);key=(id(m),size)
        if video!=self.last_video or key!=self.last_display_size:
            im=framebuffer(m.ram)
            self.machine_photo=ImageTk.PhotoImage(im.resize(size,Image.Resampling.NEAREST))
            if not hasattr(self,'display_item'):
                self.display_item=self.display.create_image(0,0)
            self.display.itemconfigure(self.display_item,image=self.machine_photo)
            self.display.coords(self.display_item,self.display.winfo_width()/2,self.display.winfo_height()/2)
            self.last_video=video;self.last_display_size=key
        extra=f'A={m.a:05d}  D={m.d:05d}  PC={m.pc:05d}' if isinstance(m,HackCPU) else m.location+f'  pile={len(m.stack)}  appels={len(m.frames)}'
        self.emu_status.set(f'{"RUN" if self.running else "PAUSE"}  {m.steps:,} instructions  {extra}')
        if isinstance(m,VideoCPU):
            self.emu_status.set(self.emu_status.get()+'\n'+m.video_status)

    def capture_changed(self):
        self.keys.clear()
        if self.machine:self.machine.ram[24576]=0
        if self.capture.get():self.display.focus_set()

    def focus_out(self,event):
        self.keys.clear()
        if self.machine:self.machine.ram[24576]=0

    def key_down(self,event):
        if event.keysym=='Escape':self.capture.set(False);self.capture_changed();return
        if not self.capture.get() or self.root.focus_get()!=self.display or not self.machine:return
        mapping={'Return':128,'BackSpace':129,'Left':130,'Up':131,'Right':132,'Down':133,'Home':134,'End':135,'Prior':136,'Next':137,'Insert':138,'Delete':139,'space':32}
        value=mapping.get(event.keysym)
        if value is None and event.char and 32<=ord(event.char)<127:value=ord(event.char)
        if value is not None:
            self.keys[event.keysym]=value;self.machine.ram[24576]=value
            return 'break'

    def key_up(self,event):
        self.keys.pop(event.keysym,None)
        if self.machine:self.machine.ram[24576]=next(reversed(self.keys.values()),0)

    def error(self,error):
        self.status.set(str(error));messagebox.showerror('Nand Asset Studio',str(error))

    def close(self):
        self.closed=True;self.running=False;self.playing=False
        self.video.close()
        self.convert_worker.close();self.code_worker.close()
        self.pool.shutdown(wait=False,cancel_futures=True)
        for callback in self.root.tk.call('after','info'):
            self.root.after_cancel(callback)
        self.root.destroy()


def main():
    root=tk.Tk();Studio(root);root.mainloop()


if __name__=='__main__':main()
