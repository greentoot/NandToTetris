"""Document actions shared by the workshop and the pixel editor."""
from pathlib import Path
from tkinter import filedialog
from artwork import pixel_overrides,apply_overrides,save_artwork,load_artwork
from editor import ArtworkEditor
from frame_ops import IMAGE_TYPES,read_frames,source_sheet


class ArtworkActions:
    def frames_ready(self):
        if self.converting or self.convert_job or self.future is not None:
            self.status.set('Attendez la fin du traitement avant de modifier les frames.');return False
        if not self.frames:
            self.status.set('Importez une première image dans l’atelier.');return False
        if self.playing:self.toggle_animation()
        return True

    def add_frames(self):
        if not self.frames_ready():return
        paths=filedialog.askopenfilenames(title='Ajouter des images après la frame sélectionnée',filetypes=IMAGE_TYPES)
        if not paths:return
        if len(paths)+len(self.frames)>256:
            self.status.set('L’atelier accepte 256 frames maximum.');return
        version=self.generation;index=self.index;settings=self.accepted_settings
        size=self.frames[0].size
        def done(data):
            if self.generation!=version or self.converting or self.convert_job:
                self.status.set('Le projet a changé pendant l’import : recommencez l’ajout.');return
            raw,binary=data;at=index+1
            originals=[self.original_frame(i) for i in range(len(self.frames))]
            self.replace_frames(self.frames[:at]+binary+self.frames[at:],
                self.base_frames[:at]+[im.copy() for im in binary]+self.base_frames[at:],
                originals[:at]+raw+originals[at:],at)
            self.status.set(f'{len(binary)} frame(s) ajoutée(s) après la sélection.')
        self.background_job(lambda:read_frames(paths,size,settings,256-len(self.frames),
            opaque=settings.mode=='Écran 512 × 256'),done)

    def delete_frame(self):
        if not self.frames_ready():return
        if len(self.frames)==1:
            self.status.set('Conservez au moins une frame : ajoutez une image avant de supprimer celle-ci.');return
        index=self.index
        keep=[i for i in range(len(self.frames)) if i!=index]
        self.replace_frames([self.frames[i] for i in keep],[self.base_frames[i] for i in keep],
            [self.original_frame(i) for i in keep],min(index,len(keep)-1))
        self.status.set(f'Frame {index+1} supprimée. Annuler frames permet de la récupérer.')

    def replace_frames(self,frames,base,originals,index):
        saved=([im.copy() for im in self.frames],[im.copy() for im in self.base_frames],
            self.accepted_source,self.accepted_settings,self.class_name.get(),self.source_path,self.index)
        source,settings=source_sheet(originals,self.accepted_settings)
        self.accept_artwork((frames,base,source,settings,self.class_name.get()),self.source_path)
        self.frame_undo=saved
        self.index=index;self.draw_preview();self.draw_filmstrip();self.schedule_code()

    def undo_frames(self):
        if not self.frames_ready():return
        saved=getattr(self,'frame_undo',None)
        if not saved:self.status.set('Aucune modification de frames à annuler.');return
        frames,base,source,settings,name,path,index=saved
        self.accept_artwork((frames,base,source,settings,name),path)
        self.frame_undo=None;self.index=index
        self.draw_preview();self.draw_filmstrip();self.schedule_code()
        self.status.set('Modification de frames annulée.')

    def open_editor(self):
        if not self.frames or self.converting or self.convert_job:
            self.status.set('Attendez la conversion avant de retoucher.');return
        previous=getattr(self,'editor_window',None)
        if previous and previous.window.winfo_exists():
            previous.window.lift();return
        if self.playing:self.toggle_animation()
        self.editor_window=ArtworkEditor(self.root,self.frames,self.index,self.generation,
            self.commit_edits,screen=self.accepted_settings.mode=='Écran 512 × 256')

    def commit_edits(self,frames,generation):
        if generation!=self.generation or self.converting or self.convert_job:
            raise ValueError('Le projet a changé : rouvrez l’éditeur pour retoucher sa version actuelle.')
        if len(frames)!=len(self.base_frames):raise ValueError('Nombre d’images incohérent.')
        self.edit_overrides=pixel_overrides(self.base_frames,frames)
        self.frames=[image.copy() for image in frames]
        self.refresh_artwork()
        self.status.set('Retouches appliquées au code, aux aperçus et aux prochains exports.')
        return self.generation

    def refresh_artwork(self):
        self.generation+=1;self.preview_cache.clear();self.thumb_cache.clear();self.code_cache.clear()
        self.code_worker.invalidate()
        self.current_code=None
        self.draw_preview();self.draw_filmstrip();self.schedule_code()

    def save_artwork_project(self):
        if not self.frames or self.converting or self.convert_job:
            self.status.set('Attendez la conversion avant d’enregistrer.');return
        path=filedialog.asksaveasfilename(title='Enregistrer l’artwork modifiable',
            defaultextension='.nandart',filetypes=[('Artwork modifiable','*.nandart')])
        if not path:return
        frames=list(self.frames);base=list(self.base_frames);source=self.accepted_source
        settings=self.accepted_settings;name=self.class_name.get()
        self.background_job(lambda:save_artwork(path,frames,base,source,settings,name),
                            lambda result:self.status.set('Artwork modifiable enregistré : '+Path(path).name))

    def open_artwork_project(self):
        path=filedialog.askopenfilename(title='Rouvrir un artwork',
            filetypes=[('Artwork ou manifeste exporté','*.nandart *.json')])
        if not path:return
        self.background_job(lambda:load_artwork(path),lambda data:self.accept_artwork(data,path))

    def accept_artwork(self,data,path):
        self.frame_undo=None
        frames,base,source,settings,name=data
        self.convert_worker.invalidate();self.code_worker.invalidate();self.converting=False
        if self.playing:self.toggle_animation()
        self.source=source;self.source_path=Path(path);self.accepted_source=source
        self.accepted_settings=settings;self.frames=frames;self.base_frames=base;self.index=0
        self.edit_overrides=pixel_overrides(base,frames)
        for key,var in self.vars.items():var.set(getattr(settings,key))
        self.background=tuple(settings.background);self.class_name.set(name)
        if self.convert_job:self.root.after_cancel(self.convert_job);self.convert_job=None
        self.filename.configure(text=Path(path).name[:35])
        self.export_button.state(['!disabled'])
        self.sync_asset_controls()
        self.stats.set(f'{frames[0].width} × {frames[0].height} px, {len(frames)} image(s), artwork ouvert')
        self.refresh_artwork();self.status.set('Artwork chargé. Vous pouvez reprendre ses retouches et l’exporter.')

    def sync_asset_controls(self):
        self.fit_control.configure(state='readonly' if self.accepted_settings.mode=='Écran 512 × 256' else 'disabled')
        for key,control in self.dimension_controls.items():
            active=(key=='scale' and self.accepted_settings.mode!='Écran 512 × 256') or self.accepted_settings.mode=='Planche de sprites'
            control.configure(state='normal' if active else 'disabled')
        if len(self.frames)>1:self.filmstrip.pack(after=self.frame_controls,fill='x',pady=(8,0))
        else:self.filmstrip.pack_forget()
