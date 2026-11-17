"""Streaming FFmpeg video-to-1-bit pipeline; no whole color movie in Python RAM."""
from dataclasses import dataclass,asdict
from pathlib import Path
from fractions import Fraction
import json
import math
import os
import shutil
import subprocess
import tempfile
import threading
import time
import zipfile
from PIL import Image,ImageChops
from core import bayer_maps

MAX_FRAMES=4096
WINDOWS_FLAGS={'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {}


class Cancelled(Exception):pass


def find_ffmpeg():
    configured=os.environ.get('FFMPEG_BINARY')
    if configured and Path(configured).is_file():return str(Path(configured).resolve())
    return shutil.which('ffmpeg')


def probe_video(path,ffmpeg=None):
    ffmpeg=ffmpeg or find_ffmpeg()
    probe=Path(ffmpeg).with_name('ffprobe.exe' if os.name=='nt' else 'ffprobe') if ffmpeg else None
    if not probe or not probe.is_file():
        located=shutil.which('ffprobe')
        if not located:return {'name':Path(path).name,'duration':None,'width':None,'height':None,'fps':None}
        probe=Path(located)
    result=subprocess.run([str(probe),'-v','error','-select_streams','v:0',
        '-show_entries','stream=width,height,avg_frame_rate,duration:format=duration',
        '-of','json',str(Path(path).resolve())],capture_output=True,timeout=15,**WINDOWS_FLAGS)
    if result.returncode:raise ValueError('Vidéo illisible : '+result.stderr.decode(errors='replace')[-1000:])
    data=json.loads(result.stdout);streams=data.get('streams',[])
    if not streams:raise ValueError('Le fichier ne contient aucune piste vidéo.')
    stream=streams[0]
    try:duration=float(stream.get('duration',data.get('format',{}).get('duration',0))) or None
    except (ValueError,TypeError):duration=None
    try:fps=float(Fraction(stream.get('avg_frame_rate','0/1')))
    except (ValueError,ZeroDivisionError):fps=None
    return {'name':Path(path).name,'duration':duration,'width':stream.get('width'),
            'height':stream.get('height'),'fps':fps}


@dataclass(frozen=True)
class VideoSettings:
    start:float=0.0
    duration:float=5.0
    fps:int=8
    width:int=256
    threshold:int=128
    contrast:float=1.0
    invert:bool=False
    dither:str='Seuil rapide'
    fit:str='Contenir'

    def validate(self):
        if not all(math.isfinite(float(v)) for v in (self.start,self.duration,self.contrast)):
            raise ValueError('Valeurs vidéo non finies.')
        if self.start<0 or not 0<self.duration<=120:raise ValueError('Début positif et extrait de 0 à 120 secondes.')
        if not isinstance(self.fps,int) or not 1<=self.fps<=30:raise ValueError('Cadence : 1 à 30 images/s.')
        if self.width not in (128,256,512):raise ValueError('Largeur vidéo : 128, 256 ou 512 pixels.')
        if not 0<=self.threshold<=255 or not .2<=self.contrast<=3:raise ValueError('Seuil ou contraste hors plage.')
        if self.dither not in ('Seuil rapide','Bayer 4 × 4'):raise ValueError('Trame vidéo inconnue.')
        if self.fit not in ('Contenir','Remplir','Étirer'):raise ValueError('Cadrage vidéo inconnu.')
        if math.ceil(self.duration*self.fps)>MAX_FRAMES:raise ValueError('Plus de 4096 images : réduisez la durée ou la cadence.')


@dataclass(frozen=True)
class VideoClip:
    width:int
    height:int
    fps:float
    frames:tuple
    source:str=''
    processing_seconds:float=0.0

    @property
    def duration(self):return len(self.frames)/self.fps

    @property
    def memory_bytes(self):return sum(map(len,self.frames))

    def image(self,index):
        return Image.frombytes('1',(self.width,self.height),self.frames[index])


def ffmpeg_filters(settings):
    settings.validate();w=settings.width;h=w//2
    filters=[f'fps={settings.fps}']
    if settings.fit=='Contenir':
        filters += [f'scale={w}:{h}:force_original_aspect_ratio=decrease:flags=fast_bilinear',
                    f'pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=white']
    elif settings.fit=='Remplir':
        filters += [f'scale={w}:{h}:force_original_aspect_ratio=increase:flags=fast_bilinear',f'crop={w}:{h}']
    else:filters += [f'scale={w}:{h}:flags=fast_bilinear']
    expression=f'clip((val-128)*{settings.contrast}+128,0,255)'
    if settings.invert:expression=f'255-({expression})'
    if settings.dither=='Seuil rapide':expression=f'if(gte({expression},{settings.threshold}),255,0)'
    filters+=['format=gray',f"lut=y='{expression}'"]
    return ','.join(filters)


class VideoEngine:
    def __init__(self,ffmpeg=None):
        self.ffmpeg=ffmpeg or find_ffmpeg();self.cancelled=threading.Event()
        self.process=None;self.lock=threading.Lock()

    def cancel(self):
        self.cancelled.set()
        with self.lock:
            if self.process and self.process.poll() is None:
                try:self.process.terminate()
                except OSError:pass

    def register(self,process):
        with self.lock:self.process=process
        if self.cancelled.is_set():self.cancel()

    def _finish(self,process):
        if process.poll() is None:process.kill()
        process.wait()
        with self.lock:
            if self.process is process:self.process=None

    def decode(self,path,settings,progress=None):
        settings.validate()
        if not self.ffmpeg:raise ValueError('FFmpeg est nécessaire pour la vidéo. Installez-le ou choisissez son exécutable.')
        if self.cancelled.is_set():raise Cancelled('Traitement annulé.')
        started=time.perf_counter();w=settings.width;h=w//2;frame_bytes=w*h
        limit=min(MAX_FRAMES,math.ceil(settings.duration*settings.fps))
        command=[self.ffmpeg,'-hide_banner','-loglevel','error','-nostdin','-threads','0',
            '-ss',str(settings.start),'-i',str(Path(path).resolve()),'-t',str(settings.duration),
            '-map','0:v:0','-an','-sn','-dn','-filter_threads','2','-vf',ffmpeg_filters(settings),
            '-frames:v',str(limit),'-fps_mode','passthrough','-pix_fmt','gray','-f','rawvideo','pipe:1']
        output=[]
        with tempfile.TemporaryFile() as errors:
            process=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=errors,**WINDOWS_FLAGS)
            self.register(process)
            try:
                while len(output)<limit:
                    if self.cancelled.is_set():raise Cancelled('Traitement annulé.')
                    raw=bytearray()
                    while len(raw)<frame_bytes:
                        chunk=process.stdout.read(frame_bytes-len(raw))
                        if not chunk:break
                        raw.extend(chunk)
                    if not raw:break
                    if len(raw)!=frame_bytes:
                        if self.cancelled.is_set():raise Cancelled('Traitement annulé.')
                        raise ValueError('Image vidéo incomplète.')
                    image=Image.frombytes('L',(w,h),bytes(raw))
                    if settings.dither!='Seuil rapide':
                        thresholds,valid=bayer_maps((w,h),settings.threshold)
                        image=ImageChops.multiply(ImageChops.subtract(image,thresholds,offset=1).point([0]+[255]*255),valid)
                    output.append(image.convert('1',dither=Image.Dither.NONE).tobytes())
                    if progress and (len(output)%4==0 or len(output)==limit):progress(len(output),limit)
                code=process.wait()
                if self.cancelled.is_set():raise Cancelled('Traitement annulé.')
                if code:
                    errors.seek(0);raise ValueError('FFmpeg : '+errors.read().decode(errors='replace')[-1500:])
                if not output:raise ValueError('Aucune image dans cet extrait. Vérifiez le début et la durée.')
            finally:
                process.stdout.close();self._finish(process)
        return VideoClip(w,h,float(settings.fps),tuple(output),Path(path).name,time.perf_counter()-started)

    def export_movie(self,clip,path,progress=None):
        if not self.ffmpeg:raise ValueError('FFmpeg est nécessaire pour cet export.')
        if self.cancelled.is_set():raise Cancelled('Export annulé.')
        path=Path(path);suffix=path.suffix.lower()
        if suffix not in ('.mp4','.gif'):raise ValueError('Choisir un fichier MP4 ou GIF.')
        with tempfile.NamedTemporaryFile(prefix=path.stem+'.',suffix=suffix,dir=path.parent,delete=False) as file:
            temporary=Path(file.name)
        command=[self.ffmpeg,'-y','-hide_banner','-loglevel','error','-f','rawvideo','-pixel_format','gray',
                 '-video_size',f'{clip.width}x{clip.height}','-framerate',str(clip.fps),'-i','pipe:0','-an']
        if suffix=='.mp4':command+=['-c:v','libx264','-preset','ultrafast','-crf','18','-pix_fmt','yuv420p']
        else:command+=['-loop','0']
        command.append(str(temporary))
        try:
            with tempfile.TemporaryFile() as errors:
                process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=errors,**WINDOWS_FLAGS)
                self.register(process)
                try:
                    for i in range(len(clip.frames)):
                        if self.cancelled.is_set():raise Cancelled('Export annulé.')
                        process.stdin.write(clip.image(i).convert('L').tobytes())
                        if progress and i%4==0:progress(i+1,len(clip.frames))
                    process.stdin.close();code=process.wait()
                    if self.cancelled.is_set():raise Cancelled('Export annulé.')
                    if code:
                        errors.seek(0);raise ValueError(errors.read().decode(errors='replace')[-1500:])
                except BrokenPipeError as error:
                    if self.cancelled.is_set():raise Cancelled('Export annulé.') from error
                    errors.seek(0);raise ValueError('FFmpeg : '+errors.read().decode(errors='replace')[-1500:]) from error
                finally:
                    try:
                        if not process.stdin.closed:process.stdin.close()
                    except BrokenPipeError:pass
                    finally:self._finish(process)
            temporary.replace(path)
        finally:
            if temporary.exists():temporary.unlink()


def save_clip(path,clip):
    path=Path(path)
    manifest={'format':'nandvideo','version':1,'width':clip.width,'height':clip.height,
        'fps':clip.fps,'frames':len(clip.frames),'source':clip.source,'packing':'Pillow 1: MSB first, 1=white, rows top-down'}
    with tempfile.NamedTemporaryFile(prefix=path.name+'.',suffix='.tmp',dir=path.parent,delete=False) as file:
        temporary=Path(file.name)
    try:
        with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED,compresslevel=1) as archive:
            archive.writestr('video.json',json.dumps(manifest,indent=2))
            with archive.open('frames.bin','w') as stream:
                for frame in clip.frames:stream.write(frame)
            archive.writestr('README.txt','Nand Asset Studio video, sans audio.\nChaque image occupe width*height/8 octets.\n'
                'Pillow: Image.frombytes("1", (width,height), image_bytes).\n'
                'Ce format est un conteneur d’assets ; il n’est pas un programme CPU Hack.\n'
                'Rouvrir dans l’onglet Video du Studio, ou importer une courte sequence dans l’atelier Jack.\n')
        temporary.replace(path)
    finally:
        if temporary.exists():temporary.unlink()


def load_clip(path):
    with zipfile.ZipFile(path) as archive:
        if archive.getinfo('video.json').file_size>100_000:raise ValueError('Manifeste vidéo trop volumineux.')
        data=json.loads(archive.read('video.json'))
        if data.get('format')!='nandvideo' or data.get('version')!=1:raise ValueError('Format vidéo non reconnu.')
        w,h,count,fps=data['width'],data['height'],data['frames'],data['fps']
        if w not in (128,256,512) or h!=w//2 or not isinstance(count,int) or not 1<=count<=MAX_FRAMES or not 1<=fps<=30:
            raise ValueError('Dimensions ou cadence vidéo invalides.')
        stride=w*h//8;member=archive.getinfo('frames.bin')
        if member.file_size!=stride*count:raise ValueError('Taille de la séquence vidéo incohérente.')
        frames=[]
        with archive.open(member) as stream:
            for _ in range(count):frames.append(stream.read(stride))
        return VideoClip(w,h,float(fps),tuple(frames),data.get('source',''))
