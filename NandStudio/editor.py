"""Resizable pixel editor for generated screens and sprite frames."""
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from PIL import Image,ImageTk,ImageDraw
from artwork import EditDocument,PALETTE

BG='#10131e';PANEL='#191e2c';CYAN='#65e1ce';TEXT='#eef2ff'


class ArtworkEditor:
    def __init__(self,parent,frames,index,generation,apply_callback,screen=False):
        self.document=EditDocument(frames);self.index=index;self.generation=generation
        self.apply_callback=apply_callback;self.screen=screen;self.last_point=None
        self.window=tk.Toplevel(parent);self.window.title('Retoucher l’artwork - Nand Asset Studio')
        self.window.geometry('1060x740');self.window.minsize(740,520);self.window.configure(bg=BG)
        self.tool=tk.StringVar(value='Crayon');self.color=tk.StringVar(value='Noir')
        self.brush=tk.IntVar(value=1);self.zoom=tk.StringVar(value='Ajuster');self.info=tk.StringVar()
        bar=tk.Frame(self.window,bg=PANEL,padx=12,pady=10);bar.pack(fill='x')
        ttk.Combobox(bar,textvariable=self.tool,values=['Crayon','Remplissage','Pipette'],state='readonly',width=13).pack(side='left',padx=(0,10))
        for color in ('Noir','Blanc','Transparent'):
            button=ttk.Radiobutton(bar,text=color,value=color,variable=self.color)
            button.pack(side='left',padx=4)
            if screen and color=='Transparent':button.state(['disabled'])
        ttk.Label(bar,text='Taille').pack(side='left',padx=(12,4))
        ttk.Spinbox(bar,from_=1,to=16,textvariable=self.brush,width=4).pack(side='left')
        zoom=ttk.Combobox(bar,textvariable=self.zoom,values=['Ajuster','100 %','200 %','400 %','800 %','1600 %'],state='readonly',width=9)
        zoom.pack(side='right');zoom.bind('<<ComboboxSelected>>',lambda e:self.draw())
        split=tk.PanedWindow(self.window,orient='vertical',bg=BG,sashwidth=8,sashrelief='flat',showhandle=True)
        split.pack(fill='both',expand=True,padx=12,pady=10)
        holder=tk.Frame(split,bg=BG);split.add(holder,minsize=160,stretch='always')
        holder.grid_rowconfigure(0,weight=1);holder.grid_columnconfigure(0,weight=1)
        self.canvas=tk.Canvas(holder,bg='#080b12',highlightthickness=0,cursor='crosshair')
        self.canvas.grid(row=0,column=0,sticky='nsew')
        horizontal=ttk.Scrollbar(holder,orient='horizontal',command=self.canvas.xview);horizontal.grid(row=1,column=0,sticky='ew')
        vertical=ttk.Scrollbar(holder,orient='vertical',command=self.canvas.yview);vertical.grid(row=0,column=1,sticky='ns')
        self.canvas.configure(xscrollcommand=horizontal.set,yscrollcommand=vertical.set)
        self.item=self.canvas.create_image(12,12,anchor='nw')
        self.canvas.bind('<Configure>',lambda e:self.draw())
        self.canvas.bind('<Button-1>',self.stroke_start)
        self.canvas.bind('<B1-Motion>',self.stroke_move)
        self.canvas.bind('<ButtonRelease-1>',self.stroke_end)
        self.canvas.bind('<Button-3>',self.erase_white)
        helpbox=tk.Frame(split,bg=PANEL,padx=14,pady=8);split.add(helpbox,minsize=42,height=65,stretch='never')
        tk.Label(helpbox,text='Dessinez sur les pixels agrandis. Clic droit : blanc. Ctrl Z / Ctrl Y : annuler / rétablir.\nLes retouches restent locales tant que vous n’appuyez pas sur Appliquer.',
                 bg=PANEL,fg=TEXT,justify='left',anchor='w',font=('Segoe UI',10)).pack(fill='both',expand=True)
        actions=tk.Frame(self.window,bg=PANEL,padx=12,pady=10);actions.pack(fill='x')
        ttk.Button(actions,text='Image précédente',command=lambda:self.change_frame(-1)).pack(side='left')
        ttk.Button(actions,text='Image suivante',command=lambda:self.change_frame(1)).pack(side='left',padx=4)
        ttk.Button(actions,text='Annuler',command=self.undo).pack(side='left',padx=(10,4))
        ttk.Button(actions,text='Rétablir',command=self.redo).pack(side='left')
        ttk.Button(actions,text='Enregistrer PNG',command=self.save_png).pack(side='right',padx=(6,0))
        ttk.Button(actions,text='Appliquer au projet',command=self.apply,style='Accent.TButton').pack(side='right')
        tk.Label(self.window,textvariable=self.info,bg=BG,fg=CYAN,anchor='w',padx=14,pady=8).pack(fill='x')
        self.window.bind('<Control-z>',lambda e:self.undo())
        self.window.bind('<Control-y>',lambda e:self.redo())
        self.window.protocol('WM_DELETE_WINDOW',self.close)
        self.draw()

    def draw(self):
        image=self.document.frames[self.index]
        width=max(1,self.canvas.winfo_width()-24);height=max(1,self.canvas.winfo_height()-24)
        self.scale=min(width/image.width,height/image.height) if self.zoom.get()=='Ajuster' else int(self.zoom.get().split()[0])/100
        # Before the first geometry pass, render at a useful default scale.
        if width<10 and self.zoom.get()=='Ajuster':self.scale=2
        size=(max(1,round(image.width*self.scale)),max(1,round(image.height*self.scale)))
        checker=Image.new('RGBA',image.size,'#c4cbd8');d=ImageDraw.Draw(checker)
        for y in range(0,image.height,8):
            for x in range(0,image.width,8):
                if (x//8+y//8)%2:d.rectangle((x,y,x+7,y+7),fill='#929eb2')
        checker.alpha_composite(image)
        enlarged=checker.resize(size,Image.Resampling.NEAREST)
        if self.scale>=8:
            d=ImageDraw.Draw(enlarged)
            for x in range(image.width+1):d.line((round(x*self.scale),0,round(x*self.scale),size[1]),fill='#626d80')
            for y in range(image.height+1):d.line((0,round(y*self.scale),size[0],round(y*self.scale)),fill='#626d80')
        self.photo=ImageTk.PhotoImage(enlarged)
        self.canvas.itemconfigure(self.item,image=self.photo)
        self.canvas.configure(scrollregion=(0,0,size[0]+24,size[1]+24))
        self.info.set(f'Image {self.index+1}/{len(self.document.frames)}, {image.width} × {image.height}, zoom {self.scale*100:.0f}%, {len(self.document.undo_stack)} modification(s)')

    def point(self,event):
        x=int((self.canvas.canvasx(event.x)-12)//self.scale)
        y=int((self.canvas.canvasy(event.y)-12)//self.scale)
        image=self.document.frames[self.index]
        return (x,y) if 0<=x<image.width and 0<=y<image.height else None

    def stroke_start(self,event):
        point=self.point(event)
        if point is None:return
        if self.tool.get()=='Pipette':
            pixel=self.document.frames[self.index].getpixel(point)
            self.color.set('Transparent' if pixel[3]==0 and not self.screen else 'Noir' if pixel[0]<128 else 'Blanc')
            return
        self.document.begin(self.index);self.last_point=point
        color=PALETTE[self.color.get()]
        if self.tool.get()=='Remplissage':
            self.document.fill(self.index,point,color);self.document.finish();self.last_point=None
        else:self.document.line(self.index,point,point,color,self.brush.get())
        self.draw()

    def stroke_move(self,event):
        if self.last_point is None:return
        point=self.point(event)
        if point is None:self.last_point=None;return
        self.document.line(self.index,self.last_point,point,PALETTE[self.color.get()],self.brush.get())
        self.last_point=point;self.draw()

    def stroke_end(self,event=None):
        self.document.finish();self.last_point=None;self.draw()

    def erase_white(self,event):
        previous=self.color.get();tool=self.tool.get();self.color.set('Blanc');self.tool.set('Crayon')
        self.stroke_start(event);self.stroke_end();self.color.set(previous);self.tool.set(tool)

    def change_frame(self,delta):
        self.document.finish();self.index=(self.index+delta)%len(self.document.frames);self.draw()

    def undo(self):
        index=self.document.undo()
        if index is not None:self.index=index
        self.draw()

    def redo(self):
        index=self.document.redo()
        if index is not None:self.index=index
        self.draw()

    def apply(self):
        self.document.finish()
        try:
            self.generation=self.apply_callback(self.document.frames,self.generation)
            self.document.changed=False;self.info.set('Retouches appliquées : aperçu, code et export mis à jour.')
            return True
        except ValueError as error:
            self.info.set(str(error)+' Vous pouvez encore enregistrer un PNG.')
            return False

    def save_png(self):
        path=filedialog.asksaveasfilename(parent=self.window,defaultextension='.png',filetypes=[('Image PNG','*.png')])
        if path:self.document.frames[self.index].save(path)

    def close(self):
        self.document.finish()
        if self.document.changed:
            answer=messagebox.askyesnocancel('Retouches','Appliquer les retouches avant de fermer ?',parent=self.window)
            if answer is None:return
            if answer and not self.apply():return
        self.window.destroy()
